"""Prediction intervals for the tabular RUL model.

Two ingredients:

1. Quantile regression. Instead of the typical RUL, a model is trained to
   predict a low value (which the truth should exceed 95% of the time) and a
   high value (which the truth should stay below 95% of the time).
2. Conformal calibration. The raw band is then widened or narrowed by one
   number, measured on engines the models did not train on, so that the band
   actually contains the truth as often as promised.

Together this is known as conformalized quantile regression (CQR).
"""

import numpy as np
import pandas as pd
from xgboost import XGBRegressor


def make_quantile_model(quantile: float, seed: int) -> XGBRegressor:
    """An XGBoost model trained to predict one quantile of RUL instead of its mean."""
    return XGBRegressor(
        objective="reg:quantileerror", quantile_alpha=quantile,
        n_estimators=400, learning_rate=0.05, max_depth=4, subsample=0.8, colsample_bytree=0.8,
        n_jobs=-1, random_state=seed,
    )


def raw_band(low_model, high_model, features: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    """Uncalibrated band; the two models are trained separately, so keep low <= high."""
    low, high = low_model.predict(features), high_model.predict(features)
    return np.minimum(low, high), np.maximum(low, high)


def conformity_scores(low: np.ndarray, high: np.ndarray, truth: np.ndarray) -> np.ndarray:
    """How far outside the band each truth lies (negative if it is inside)."""
    return np.maximum(low - truth, truth - high)


def conformal_correction(scores: np.ndarray, coverage: float) -> float:
    """The amount to add to both sides so the band covers `coverage` of unseen cases."""
    n = len(scores)
    level = min(1.0, np.ceil((n + 1) * coverage) / n)   # finite-sample adjustment
    return float(np.quantile(scores, level, method="higher"))


def calibrated_band(
    low: np.ndarray, high: np.ndarray, correction: float, lower_limit: float = 0.0, upper_limit: float | None = None
) -> tuple[np.ndarray, np.ndarray]:
    """Apply the correction and keep the band inside the range RUL can take."""
    return np.clip(low - correction, lower_limit, upper_limit), np.clip(high + correction, lower_limit, upper_limit)


def enclose_point(low: np.ndarray, high: np.ndarray, point: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Stretch a range, where needed, so that it contains the point estimate.

    The point model and the two quantile models are trained separately, so now
    and then the estimate falls just outside its own range. A range that
    excludes its own estimate would confuse a reader, and stretching can only
    make the range more cautious.
    """
    return np.minimum(low, point), np.maximum(high, point)
