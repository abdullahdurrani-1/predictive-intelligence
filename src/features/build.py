"""Data preparation and feature engineering for C-MAPSS.

Every function here is *causal*: a value computed for cycle t uses only that
engine's readings from cycles 1..t. Nothing looks into an engine's future, and
nothing mixes information between engines. That is what keeps the features
usable on an engine that is still in service.
"""

import numpy as np
import pandas as pd


def cap_rul(rul: pd.Series, cap: int | None) -> pd.Series:
    """Limit the RUL label to at most `cap` cycles (no change if cap is None).

    Early in life the sensors do not yet show how much life remains, so every
    cycle above the cap is labelled simply as "healthy" with the cap value.
    """
    return rul if cap is None else rul.clip(upper=cap)


def add_rolling_features(frame: pd.DataFrame, sensors: list[str], window: int) -> pd.DataFrame:
    """Add a rolling mean and rolling standard deviation for each sensor.

    The mean smooths out noise and exposes the slow trend. The standard
    deviation describes how unsettled the recent readings are. During an
    engine's first cycles the window is simply shorter.
    """
    grouped = frame.groupby("engine_id")[sensors]
    rolling_mean = grouped.rolling(window, min_periods=1).mean().reset_index(level=0, drop=True)
    rolling_std = grouped.rolling(window, min_periods=2).std().reset_index(level=0, drop=True)

    result = frame.copy()
    result[[f"{name}_mean{window}" for name in sensors]] = rolling_mean
    # The very first cycle has no spread to measure yet.
    result[[f"{name}_std{window}" for name in sensors]] = rolling_std.fillna(0.0)
    return result


def add_baseline_change(frame: pd.DataFrame, sensors: list[str], baseline_cycles: int = 20) -> pd.DataFrame:
    """Add each sensor's change from that engine's own early-life level.

    The baseline is the engine's average over its first `baseline_cycles`
    cycles. Before that many cycles exist, the average of the cycles seen so
    far is used, so the feature never looks ahead.
    """
    running_mean = frame.groupby("engine_id")[sensors].expanding().mean().reset_index(level=0, drop=True)
    # Freeze the baseline once the early-life period is over.
    still_early = frame["cycle"] <= baseline_cycles
    baseline = running_mean.where(still_early).groupby(frame["engine_id"]).ffill()

    result = frame.copy()
    result[[f"{name}_delta" for name in sensors]] = frame[sensors] - baseline
    return result


def make_windows(
    frame: pd.DataFrame,
    feature_columns: list[str],
    window: int,
    label_column: str | None = None,
    last_only: bool = False,
) -> tuple[np.ndarray, np.ndarray | None, np.ndarray]:
    """Cut each engine's history into fixed-length windows for sequence models.

    Each window holds `window` consecutive cycles and is labelled with the RUL
    at its final cycle. An engine with fewer cycles than the window is padded
    at the start by repeating its first reading.

    Returns (windows, labels, engine_ids). `windows` has shape
    (number of windows, window, number of features). With `last_only=True`
    only the most recent window of each engine is returned, which is how a
    test engine is scored.
    """
    windows, labels, engine_ids = [], [], []
    for engine_id, engine in frame.groupby("engine_id", sort=True):
        values = engine[feature_columns].to_numpy(dtype=np.float32)
        if len(values) < window:
            padding = np.repeat(values[:1], window - len(values), axis=0)
            values = np.vstack([padding, values])
        targets = engine[label_column].to_numpy(dtype=np.float32) if label_column else None

        last_end = len(values)
        first_end = last_end if last_only else window
        for end in range(first_end, last_end + 1):
            windows.append(values[end - window:end])
            engine_ids.append(engine_id)
            if targets is not None:
                # Padding only ever adds rows at the front, so count back from the end.
                labels.append(targets[len(targets) - (last_end - end) - 1])

    stacked_labels = np.asarray(labels, dtype=np.float32) if label_column else None
    return np.stack(windows), stacked_labels, np.asarray(engine_ids)


def build_tabular_features(
    frame: pd.DataFrame, sensors: list[str], rolling_window: int, baseline_cycles: int
) -> tuple[pd.DataFrame, list[str]]:
    """Apply the Phase 4 feature recipe and return (table, feature column names).

    Features: the raw sensors, their rolling mean and standard deviation, and
    their change from the engine's own early-life baseline.
    """
    table = add_rolling_features(frame, sensors, rolling_window)
    table = add_baseline_change(table, sensors, baseline_cycles)
    suffixes = (f"_mean{rolling_window}", f"_std{rolling_window}", "_delta")
    features = sensors + [name for name in table.columns if name.endswith(suffixes)]
    return table, features
