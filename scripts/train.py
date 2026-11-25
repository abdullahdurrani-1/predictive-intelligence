"""Retraining workflow: rebuild the production models from the raw data.

Run from the project root:
    python scripts/train.py

It verifies the raw data, trains the point and quantile models, calibrates the
prediction range on out-of-fold engines, scores everything on the test set,
and writes the models together with a registry entry that records exactly
what was trained, on which data, and how well it did.

A new model is only *promoted* (copied over the models the API serves) if its
test RMSE is not worse than the currently registered one by more than the
tolerance below. Otherwise the candidate is kept for inspection and the
serving models are left alone.
"""

import argparse
import hashlib
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src import config  # noqa: E402
from src.data.cmapss import add_training_rul, load_subset  # noqa: E402
from src.data.splits import engine_folds  # noqa: E402
from src.evaluation.metrics import mae, nasa_score, rmse  # noqa: E402
from src.features.build import build_tabular_features, cap_rul  # noqa: E402
from src.models.uncertainty import (  # noqa: E402
    calibrated_band, conformal_correction, conformity_scores, make_quantile_model, raw_band)
from xgboost import XGBRegressor  # noqa: E402

PROMOTION_TOLERANCE_CYCLES = 0.5
TARGET_COVERAGE = 0.90


def verify_raw_data() -> dict:
    """Check the raw files against the recorded checksums; return the ones used for training."""
    recorded = dict(line.split("  ", 1)[::-1] for line in (ROOT / "data" / "checksums.sha256").read_text().splitlines())
    used = {}
    for name in ["train_FD001.txt", "test_FD001.txt", "RUL_FD001.txt"]:
        actual = hashlib.sha256((ROOT / "data" / "raw" / name).read_bytes()).hexdigest()
        if actual != recorded[name]:
            raise SystemExit(f"Raw file {name} does not match its recorded checksum. Refusing to train.")
        used[name] = actual
    return used


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--params", type=Path, help="JSON file of XGBoost settings (default: project defaults)")
    parser.add_argument("--no-promote", action="store_true", help="train and register, but do not replace serving models")
    arguments = parser.parse_args()

    data_hashes = verify_raw_data()
    params = dict(n_estimators=400, learning_rate=0.05, max_depth=4, subsample=0.8, colsample_bytree=0.8)
    if arguments.params:
        params.update(json.loads(arguments.params.read_text()))

    train, test, test_rul = load_subset("FD001")
    table, features = build_tabular_features(add_training_rul(train), config.FD001_SENSORS,
                                             config.ROLLING_WINDOW, config.BASELINE_CYCLES)
    table["target"] = cap_rul(table["rul"], config.RUL_CAP)

    def point_model():
        return XGBRegressor(**params, n_jobs=-1, random_state=config.RANDOM_SEED)

    # Out-of-fold predictions give honest validation scores and the calibration set for the range.
    fold_rmse, out_low, out_high = [], np.zeros(len(table)), np.zeros(len(table))
    for train_rows, held_out in engine_folds(table):
        fold = table.iloc[train_rows]
        predicted = np.clip(point_model().fit(fold[features], fold["target"]).predict(table.iloc[held_out][features]), 0, config.RUL_CAP)
        fold_rmse.append(rmse(table.iloc[held_out]["target"], predicted))
        low = make_quantile_model(0.05, config.RANDOM_SEED).fit(fold[features], fold["target"])
        high = make_quantile_model(0.95, config.RANDOM_SEED).fit(fold[features], fold["target"])
        out_low[held_out], out_high[held_out] = raw_band(low, high, table.iloc[held_out][features])
    usable = (table["cycle"] >= 31).to_numpy()
    correction = conformal_correction(conformity_scores(out_low[usable], out_high[usable], table["target"].to_numpy()[usable]), TARGET_COVERAGE)

    models = {
        "point": point_model().fit(table[features], table["target"]),
        "q05": make_quantile_model(0.05, config.RANDOM_SEED).fit(table[features], table["target"]),
        "q95": make_quantile_model(0.95, config.RANDOM_SEED).fit(table[features], table["target"]),
    }

    test_table, _ = build_tabular_features(test, config.FD001_SENSORS, config.ROLLING_WINDOW, config.BASELINE_CYCLES)
    last = test_table.groupby("engine_id").tail(1).merge(test_rul, on="engine_id")
    truth = last["true_rul"].to_numpy()
    predicted = np.clip(models["point"].predict(last[features]), 0, config.RUL_CAP)
    low, high = calibrated_band(*raw_band(models["q05"], models["q95"], last[features]), correction, 0, config.RUL_CAP)
    truth_capped = np.minimum(truth, config.RUL_CAP)
    metrics = {
        "cv_rmse": round(float(np.mean(fold_rmse)), 3), "test_rmse": round(rmse(truth, predicted), 3),
        "test_mae": round(mae(truth, predicted), 3), "test_nasa_score": round(nasa_score(truth, predicted), 1),
        "test_range_coverage_percent": round(float(((truth_capped >= low) & (truth_capped <= high)).mean() * 100), 1),
        "test_range_width": round(float((high - low).mean()), 1),
    }

    version = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    candidate_dir = ROOT / "models" / "registry" / version
    candidate_dir.mkdir(parents=True)
    for name, model in models.items():
        joblib.dump(model, candidate_dir / f"fd001_xgboost_{name}.joblib")
    settings = {
        "subset": "FD001", "target_coverage": TARGET_COVERAGE, "rul_cap": config.RUL_CAP,
        "cqr_correction_cycles": round(float(correction), 4),
        "calibration": "5-fold out-of-fold predictions by engine, rows with cycle >= 31",
        "test_coverage_capped_truth_percent": metrics["test_range_coverage_percent"],
        "test_average_width_cycles": metrics["test_range_width"], "features": features,
    }
    (candidate_dir / "fd001_uncertainty.json").write_text(json.dumps(settings, indent=1))

    registry_path = ROOT / "models" / "registry" / "registry.json"
    registry = json.loads(registry_path.read_text()) if registry_path.exists() else {"serving": None, "versions": []}
    serving = next((v for v in registry["versions"] if v["version"] == registry["serving"]), None)
    promote = not arguments.no_promote and (
        serving is None or metrics["test_rmse"] <= serving["metrics"]["test_rmse"] + PROMOTION_TOLERANCE_CYCLES)

    registry["versions"].append({"version": version, "params": params, "metrics": metrics, "data_sha256": data_hashes,
                                 "settings": {"rul_cap": config.RUL_CAP, "rolling_window": config.ROLLING_WINDOW,
                                              "baseline_cycles": config.BASELINE_CYCLES, "seed": config.RANDOM_SEED},
                                 "promoted": promote})
    if promote:
        for name in models:
            shutil.copy2(candidate_dir / f"fd001_xgboost_{name}.joblib", ROOT / "models" / f"fd001_xgboost_{name}.joblib")
        shutil.copy2(candidate_dir / "fd001_uncertainty.json", ROOT / "experiments" / "fd001_uncertainty.json")
        registry["serving"] = version
    registry_path.write_text(json.dumps(registry, indent=1))

    print(json.dumps({"version": version, "promoted": promote, **metrics}, indent=1))
    if not promote and not arguments.no_promote:
        print(f"Not promoted: test RMSE is more than {PROMOTION_TOLERANCE_CYCLES} cycles worse than serving version {registry['serving']}.")


if __name__ == "__main__":
    main()
