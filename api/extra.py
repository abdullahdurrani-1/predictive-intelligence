"""Endpoints for the web application's research, sensor, model, monitoring, assistant and settings pages.

Everything here is read from files the notebooks and scripts produced, or
computed from the data on request. Nothing is hard-coded.
"""

import json
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from src import config
from src.assistant.chat import chat, provider_status
from src.assistant.knowledge import LIMITATIONS, SAFETY_NOTE
from src.data.cmapss import SENSOR_INFO, add_training_rul, load_subset
from src.explainability.shap_explain import by_sensor, explain, kind_of
from src.features.build import build_tabular_features
from src.monitoring.drift import drift_report, prediction_summary
from src.service.engine_service import EngineService

router = APIRouter()
_service: EngineService | None = None


def get_service() -> EngineService:
    global _service
    if _service is None:
        _service = EngineService()
    return _service


def table(path: Path, index: str | None = None) -> list[dict] | None:
    """A CSV as a list of rows, or None if the notebook that writes it has not been run."""
    if not path.exists():
        return None
    frame = pd.read_csv(path)
    return json.loads(frame.round(4).to_json(orient="records"))


# ---- sensors -------------------------------------------------------------------------

@lru_cache
def sensor_analysis() -> dict:
    service = get_service()
    train, _, _ = load_subset("FD001", service.root / "data" / "raw")
    labelled = add_training_rul(train)
    sensors = service.sensors

    featured, _ = build_tabular_features(labelled, sensors, config.ROLLING_WINDOW, config.BASELINE_CYCLES)
    sample = featured.sample(3000, random_state=config.RANDOM_SEED)
    contributions, _ = explain(service.point_model, sample[service.features])
    per_sensor = by_sensor(contributions).abs().mean()
    kinds = contributions.abs().mean().groupby(kind_of).sum()

    trend = labelled[sensors].corrwith(labelled["rul"], method="spearman")
    return {
        "sensors": sensors,
        "labels": [f"S{name.split('_')[1]} {SENSOR_INFO[name][0]}" for name in sensors],
        "correlation": labelled[sensors].corr().round(3).to_numpy().tolist(),
        "trend_with_rul": {name: round(float(trend[name]), 3) for name in sensors},
        "model_reliance_cycles": {name: round(float(per_sensor[name]), 2) for name in sensors},
        "reliance_by_feature_kind_percent": {kind: round(float(value / kinds.sum() * 100), 1) for kind, value in kinds.items()},
        "basis": "FD001 training engines. Correlations are Pearson between sensors and Spearman with remaining life. "
                 "Model reliance is the mean absolute SHAP contribution over 3,000 training rows, summed per sensor.",
        "caution": "Correlation and model reliance describe association. Neither shows that a sensor identifies a mechanical fault.",
    }


@router.get("/sensors/analysis")
def sensors_analysis() -> dict:
    return sensor_analysis()


# ---- research ------------------------------------------------------------------------

@router.get("/research")
def research(service: EngineService = Depends(get_service)) -> dict:
    experiments = service.root / "experiments"
    tuned = experiments / "fd001_xgboost_tuned_params.json"
    deep_runs = sorted((experiments / "deep_runs").glob("*.json")) if (experiments / "deep_runs").exists() else []
    curves = []
    for path in deep_runs:
        if path.stem.endswith("_delta_seed0"):
            run = json.loads(path.read_text())
            curves.append({"model": path.stem.split("_")[1].upper(), "train_rmse": run["train_rmse"],
                           "validation_rmse": run["validation_rmse"], "best_epoch": run["best_epoch"]})
    return {
        "ml_test": table(experiments / "fd001_ml_baselines_test.csv"),
        "ml_cv": table(experiments / "fd001_ml_baselines_cv.csv"),
        "ml_predictions": table(experiments / "fd001_ml_baselines_test_predictions.csv"),
        "deep_test": table(experiments / "fd001_deep_test.csv"),
        "deep_validation": table(experiments / "fd001_deep_validation.csv"),
        "deep_predictions": table(experiments / "fd001_deep_test_predictions.csv"),
        "deep_learning_curves": curves,
        "uncertainty_test": table(experiments / "fd001_uncertainty_test.csv"),
        "all_subsets": table(experiments / "all_subsets_xgboost.csv"),
        "all_subsets_transfer": table(experiments / "all_subsets_transfer_rmse.csv"),
        "all_subsets_uncertainty": table(experiments / "all_subsets_uncertainty.csv"),
        "all_subsets_deep": table(experiments / "all_subsets_deep.csv"),
        "tuned_parameters": json.loads(tuned.read_text()) if tuned.exists() else None,
        "experiment_counts": {"neural network runs saved (FD001)": len(deep_runs),
                              "neural network runs saved (all subsets)":
                                  len(list((experiments / "deep_generalisation_runs").glob("*.json")))
                                  if (experiments / "deep_generalisation_runs").exists() else 0},
        "source": "Tables written by notebooks 05, 06, 07, 09 and 10 into experiments/. A missing table means that notebook has not been run.",
    }


# ---- models --------------------------------------------------------------------------

@router.get("/models")
def models(service: EngineService = Depends(get_service)) -> dict:
    registry_path = service.root / "models" / "registry" / "registry.json"
    registry = json.loads(registry_path.read_text()) if registry_path.exists() else {"serving": None, "versions": []}
    served_file = service.root / "models" / "fd001_xgboost_point.joblib"
    booster_params = service.point_model.get_params()
    return {
        "served_model": {
            "name": "XGBoost regressor on engineered sensor features",
            "architecture": {
                "type": "Gradient-boosted decision trees",
                "trees": booster_params.get("n_estimators"), "max_depth": booster_params.get("max_depth"),
                "learning_rate": booster_params.get("learning_rate"),
                "inputs": f"{len(service.features)} features from {len(service.sensors)} sensors: current reading, "
                          f"{config.ROLLING_WINDOW}-flight average and variability, change from the engine's first "
                          f"{config.BASELINE_CYCLES} flights",
                "companions": "Two further models estimate the 5% and 95% quantiles for the range",
            },
            "training_data": "NASA C-MAPSS FD001 training set: 100 simulated engines, 20,631 rows",
            "target": f"Remaining useful life capped at {service.cap} flights",
            "validation": "5-fold cross-validation by whole engine; test set of 100 engines scored once",
            "file_last_written": pd.Timestamp(served_file.stat().st_mtime, unit="s", tz="UTC").isoformat(timespec="seconds"),
            "registry_version": registry["serving"] or "not promoted through the registry (written by notebook 09)",
            "range": {"method": "Conformalized quantile regression",
                      "target_percent": round(service.settings["target_coverage"] * 100),
                      "measured_percent": service.settings["test_coverage_capped_truth_percent"],
                      "average_width_flights": service.settings["test_average_width_cycles"]},
            "typical_error_flights": service._typical_error(),
        },
        "registry": registry["versions"],
        "limitations": LIMITATIONS + [
            "It cannot predict more than 125 flights; beyond that it reports a minimum.",
            "A sensor stuck at a healthy value makes it more optimistic without warning (notebook 07).",
            "It needs the engine's first 20 flights on record for its most important features.",
            "Only FD001 (one flight condition, one fault mode) is served.",
        ],
        "notice": SAFETY_NOTE,
    }


# ---- monitoring ----------------------------------------------------------------------

@router.get("/monitoring")
def monitoring(inject_drift: bool = False, service: EngineService = Depends(get_service)) -> dict:
    """Drift of incoming early-life readings against the training data, and a summary of predictions served."""
    train, test, _ = load_subset("FD001", service.root / "data" / "raw")
    reference = train[train["cycle"] <= 30]
    incoming = test[test["cycle"] <= 30].copy()
    if inject_drift:
        incoming["sensor_11"] += reference["sensor_11"].std()
    report = drift_report(reference, incoming, service.sensors)
    report["symbol"] = [SENSOR_INFO[name][0] for name in report["feature"]]

    log_path = service.root / "monitoring" / "prediction_log.jsonl"
    predictions, recent = None, []
    if log_path.exists() and log_path.stat().st_size:
        log = pd.read_json(log_path, lines=True)
        predictions = prediction_summary(log)
        recent = json.loads(log.tail(12).iloc[::-1].to_json(orient="records", date_format="iso"))
    return {
        "drift": json.loads(report.round(4).to_json(orient="records")),
        "largest_psi": float(report["psi"].max()),
        "alert": bool((report["verdict"] == "LARGE CHANGE").any()),
        "drift_injected": inject_drift,
        "thresholds": {"no_meaningful_change_below": 0.10, "large_change_above": 0.25},
        "reference": f"{len(reference):,} early-life rows from the 100 training engines",
        "incoming": f"{len(incoming):,} early-life rows from the 100 test engines, standing in for newly arrived readings",
        "predictions": predictions, "recent_predictions": recent,
        "explanation": "The Population Stability Index compares the spread of each sensor in incoming data with the "
                       "training data. Only the first 30 flights are compared, because later readings differ for a "
                       "legitimate reason: engines at different stages of wear.",
    }


# ---- assistant and settings ------------------------------------------------------------

class ChatMessage(BaseModel):
    role: str = Field(pattern="^(user|assistant)$")
    content: str = Field(min_length=1, max_length=4000)


class ChatRequest(BaseModel):
    engine_id: int
    cycle: int | None = Field(default=None, ge=1)
    messages: list[ChatMessage] = Field(min_length=1, max_length=40)
    plain_language: bool = False
    use_language_model: bool = True


@router.post("/assistant/chat")
def assistant_chat(body: ChatRequest, service: EngineService = Depends(get_service)) -> dict:
    if body.messages[-1].role != "user":
        raise HTTPException(status_code=422, detail="The last message must be from the user.")
    if body.engine_id not in service.engine_ids():
        raise HTTPException(status_code=404, detail=f"No engine with id {body.engine_id}")
    return chat(service, body.engine_id, body.cycle, [m.model_dump() for m in body.messages],
                plain=body.plain_language, use_language_model=body.use_language_model)


@router.get("/settings")
def settings(service: EngineService = Depends(get_service)) -> dict:
    checksum_file = service.root / "data" / "checksums.sha256"
    return {
        "assistant": provider_status(),
        "data": {"source": "NASA C-MAPSS simulated turbofan benchmark", "served_subset": "FD001",
                 "engines": len(service.engine_ids()), "raw_file_checksums_recorded": checksum_file.exists()},
        "model_settings": {"rul_cap_flights": config.RUL_CAP, "rolling_window_flights": config.ROLLING_WINDOW,
                           "baseline_flights": config.BASELINE_CYCLES, "random_seed": config.RANDOM_SEED},
        "notice": SAFETY_NOTE,
    }
