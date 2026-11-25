"""The engine health service: everything the API, dashboard and assistant know about an engine.

It turns a raw sensor history into a small dictionary of *facts*: the RUL
estimate, its range, a status band, and the sensors that drove the estimate.
The assistant is only ever allowed to talk about what is in that dictionary,
which is what keeps its answers tied to real model output.
"""

import json
from functools import cached_property
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from src import config
from src.assistant.knowledge import LIMITATIONS, status_for
from src.data.cmapss import SENSOR_INFO, find_project_root, load_subset
from src.explainability.shap_explain import explain, top_reasons
from src.features.build import build_tabular_features
from src.models.uncertainty import calibrated_band, enclose_point, raw_band
from src.service.validation import DataValidator

MINIMUM_HISTORY = 31   # shortest history the models were evaluated on


class EngineService:
    """Loads the trained models once and answers questions about engines."""

    def __init__(self, project_root: Path | None = None):
        self.root = project_root or find_project_root()
        models = self.root / "models"
        self.point_model = joblib.load(models / "fd001_xgboost_point.joblib")
        self.low_model = joblib.load(models / "fd001_xgboost_q05.joblib")
        self.high_model = joblib.load(models / "fd001_xgboost_q95.joblib")
        self.settings = json.loads((self.root / "experiments" / "fd001_uncertainty.json").read_text())
        self.features = self.settings["features"]
        self.cap = self.settings["rul_cap"]
        self.sensors = config.FD001_SENSORS

    @cached_property
    def validator(self) -> DataValidator:
        """Knows what normal readings look like, from the engines the model was trained on."""
        train, _, _ = load_subset("FD001", self.root / "data" / "raw")
        return DataValidator(train, self.sensors)

    # ---- the demonstration fleet -------------------------------------------------

    @cached_property
    def _fleet(self) -> pd.DataFrame:
        """The FD001 test engines: histories that stop before failure."""
        _, test, labels = load_subset("FD001", self.root / "data" / "raw")
        self._labels = labels.set_index("engine_id")["true_rul"]
        return test

    def benchmark_true_rul(self, engine_id: int) -> int:
        """True remaining life at the last recorded cycle, from the benchmark answer file.

        It exists only because the data is a finished simulation; it would not
        be known for an engine in service.
        """
        self._fleet   # make sure the labels are loaded
        return int(self._labels.loc[engine_id])

    @cached_property
    def fleet_summary(self) -> list[dict]:
        """Latest estimate, range and status for every engine in the fleet."""
        latest = self._featured(self._fleet).groupby("engine_id").tail(1)
        predictions = self.predict_rows(latest)
        rows = []
        for engine_id, prediction in zip(latest["engine_id"], predictions.itertuples()):
            estimate = int(round(prediction.estimate))
            low, high = int(np.floor(prediction.low)), int(np.ceil(prediction.high))
            open_ended = high >= self.cap
            status = status_for(estimate, low, open_ended)
            rows.append({"engine_id": int(engine_id), "cycles_recorded": int(prediction.cycle),
                         "estimate_cycles": estimate, "range_low_cycles": low,
                         "range_high_cycles": None if open_ended else high, "range_is_open_ended": open_ended,
                         "status_key": status["key"], "status_label": status["label"]})
        return rows

    def engine_ids(self) -> list[int]:
        return sorted(int(i) for i in self._fleet["engine_id"].unique())

    def history(self, engine_id: int) -> pd.DataFrame:
        engine = self._fleet[self._fleet["engine_id"] == engine_id]
        if engine.empty:
            raise KeyError(f"No engine with id {engine_id}")
        return engine.reset_index(drop=True)

    # ---- prediction ----------------------------------------------------------------

    def _featured(self, history: pd.DataFrame) -> pd.DataFrame:
        table, _ = build_tabular_features(history, self.sensors, config.ROLLING_WINDOW, config.BASELINE_CYCLES)
        return table

    def predict_rows(self, featured: pd.DataFrame) -> pd.DataFrame:
        """Estimate and 90% range for each row of an already-featured history."""
        rows = featured[self.features]
        point = np.clip(self.point_model.predict(rows), 0, self.cap)
        low, high = raw_band(self.low_model, self.high_model, rows)
        low, high = calibrated_band(low, high, self.settings["cqr_correction_cycles"], 0, self.cap)
        low, high = enclose_point(low, high, point)
        return pd.DataFrame({"cycle": featured["cycle"].to_numpy(), "estimate": point, "low": low, "high": high})

    def trajectory(self, engine_id: int) -> pd.DataFrame:
        """How the estimate evolved over the engine's recorded life."""
        predictions = self.predict_rows(self._featured(self.history(engine_id)))
        return predictions[predictions["cycle"] >= MINIMUM_HISTORY].reset_index(drop=True)

    # ---- the fact sheet ------------------------------------------------------------

    def assess(self, history: pd.DataFrame, engine_label: str = "engine") -> dict:
        """Build the fact sheet for one engine from its raw sensor history."""
        history = history.sort_values("cycle").reset_index(drop=True)
        featured = self._featured(history)
        latest = featured.tail(1)
        prediction = self.predict_rows(latest).iloc[0]

        estimate = int(round(float(prediction["estimate"])))
        low, high = int(np.floor(prediction["low"])), int(np.ceil(prediction["high"]))
        open_ended = high >= self.cap     # a range touching the cap means "this many or more"
        status = status_for(estimate, low, open_ended)

        contributions, model_average = explain(self.point_model, latest[self.features])
        reasons = top_reasons(contributions.iloc[0], count=4)
        for reason in reasons:
            reason.update(self._sensor_change(history, reason["sensor"]))

        cycles_recorded = int(history["cycle"].max())
        return {
            "engine": engine_label,
            "data_source": "NASA C-MAPSS FD001 simulated benchmark data (not a real aircraft)",
            "cycles_recorded": cycles_recorded,
            "limited_history": cycles_recorded < MINIMUM_HISTORY,
            "data_warnings": self.validator.check(history).warnings,
            "estimate_cycles": estimate,
            "range_low_cycles": low,
            "range_high_cycles": None if open_ended else high,
            "range_is_open_ended": open_ended,
            "range_confidence_percent": int(round(self.settings["target_coverage"] * 100)),
            "rul_cap_cycles": self.cap,
            "status": status,
            "model_average_estimate_cycles": int(round(model_average)),
            "main_reasons": reasons,
            "model": {
                "name": "XGBoost on engineered sensor features",
                "typical_error_cycles": self._typical_error(),
                "range_method": "conformalized quantile regression",
                "measured_range_coverage_percent": self.settings["test_coverage_capped_truth_percent"],
            },
            "limitations": LIMITATIONS,
        }

    def report(self, engine_id: int, cycle: int | None = None) -> dict:
        """Fact sheet for a fleet engine as of `cycle` (default: its last recorded cycle).

        Looking at an earlier cycle uses only the readings up to that cycle,
        exactly as if the later flights had not happened yet.
        """
        history = self.history(engine_id)
        last = int(history["cycle"].max())
        cycle = last if cycle is None else cycle
        if not 1 <= cycle <= last:
            raise ValueError(f"Engine {engine_id} has recorded cycles 1 to {last}")
        facts = self.assess(history[history["cycle"] <= cycle], engine_label=f"Engine {engine_id}")
        facts["engine_id"] = engine_id
        facts["last_recorded_cycle"] = last
        facts["is_latest_cycle"] = cycle == last
        return facts

    # ---- helpers -------------------------------------------------------------------

    def _sensor_change(self, history: pd.DataFrame, sensor: str) -> dict:
        """How a sensor's recent level compares with the engine's own early-life level."""
        baseline = float(history.loc[history["cycle"] <= config.BASELINE_CYCLES, sensor].mean())
        recent = float(history[sensor].tail(config.ROLLING_WINDOW).mean())
        change_percent = (recent - baseline) / baseline * 100 if baseline else 0.0
        return {
            "unit": SENSOR_INFO[sensor][2],
            "early_life_level": round(baseline, 2),
            "recent_level": round(recent, 2),
            "change_percent": round(change_percent, 2),
            "movement": "higher than" if recent > baseline else "lower than",
        }

    def _typical_error(self) -> int | None:
        """Mean absolute error of the model on the FD001 test set, from the saved results."""
        results = self.root / "experiments" / "fd001_ml_baselines_test.csv"
        if not results.exists():
            return None
        table = pd.read_csv(results, index_col="model")
        return int(round(float(table.loc["XGBoost", "MAE"])))
