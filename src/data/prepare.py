"""One preparation recipe that works for all four C-MAPSS subsets.

FD001 and FD003 have a single flight condition, so regime scaling reduces to
ordinary standardisation there. Using the same recipe everywhere means a
model trained on one subset can be applied to another.
"""

import pandas as pd

from src import config
from src.data.cmapss import SENSOR_COLUMNS, add_training_rul, load_subset
from src.features.build import build_tabular_features, cap_rul
from src.features.regimes import RegimeScaler

# Sensors that vary (within at least one flight condition) in every subset.
# Sensors 1, 5, 18, 19 are constant everywhere; 10 and 16 are constant in FD001.
COMMON_SENSORS = [
    "sensor_2", "sensor_3", "sensor_4", "sensor_6", "sensor_7", "sensor_8", "sensor_9", "sensor_11",
    "sensor_12", "sensor_13", "sensor_14", "sensor_15", "sensor_17", "sensor_20", "sensor_21",
]


def prepare_subset(subset: str, sensors: list[str] | None = None, normalise: bool = True) -> dict:
    """Load one subset and return model-ready tables.

    Returns a dict with:
      train        training table with features, `rul` and capped `target`
      test_last    one row per test engine (its last recorded cycle) with features and `true_rul`
      test         full test table with features (for window models)
      features     names of the feature columns
      scaler       the fitted RegimeScaler (None if normalise=False)
    """
    sensors = sensors or COMMON_SENSORS
    train, test, test_rul = load_subset(subset)

    scaler = None
    if normalise:
        scaler = RegimeScaler().fit(train, SENSOR_COLUMNS)   # training engines only
        train, test = scaler.transform(train), scaler.transform(test)

    train_table, features = build_tabular_features(
        add_training_rul(train), sensors, config.ROLLING_WINDOW, config.BASELINE_CYCLES)
    train_table["target"] = cap_rul(train_table["rul"], config.RUL_CAP)

    test_table, _ = build_tabular_features(test, sensors, config.ROLLING_WINDOW, config.BASELINE_CYCLES)
    test_last = test_table.groupby("engine_id").tail(1).merge(test_rul, on="engine_id").reset_index(drop=True)

    return {"subset": subset, "train": train_table, "test": test_table, "test_last": test_last,
            "features": features, "sensors": sensors, "scaler": scaler}
