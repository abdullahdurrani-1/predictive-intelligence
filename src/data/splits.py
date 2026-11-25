"""Engine-wise data splitting.

Rows from one engine are strongly related to each other, so an engine must be
entirely in training or entirely in validation. Splitting individual rows at
random would let a model see cycles 1-100 and 102-200 of an engine and then be
"tested" on cycle 101, which says nothing about a new engine.
"""

import numpy as np
import pandas as pd
from sklearn.model_selection import GroupKFold

RANDOM_SEED = 42


def holdout_engine_split(
    frame: pd.DataFrame, validation_fraction: float = 0.2, seed: int = RANDOM_SEED
) -> tuple[np.ndarray, np.ndarray]:
    """Return (training engine ids, validation engine ids), chosen at random by engine."""
    engine_ids = np.sort(frame["engine_id"].unique())
    shuffled = np.random.default_rng(seed).permutation(engine_ids)
    validation_count = int(round(len(engine_ids) * validation_fraction))
    return np.sort(shuffled[validation_count:]), np.sort(shuffled[:validation_count])


def engine_folds(frame: pd.DataFrame, n_splits: int = 5, seed: int = RANDOM_SEED):
    """Yield (train row positions, validation row positions) with whole engines per fold."""
    splitter = GroupKFold(n_splits=n_splits, shuffle=True, random_state=seed)
    yield from splitter.split(frame, groups=frame["engine_id"])
