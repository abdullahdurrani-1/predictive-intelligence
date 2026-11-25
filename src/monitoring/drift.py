"""Data-drift and prediction monitoring.

A model is only reliable while the engines it sees resemble the engines it was
trained on. Drift monitoring compares recent inputs with a reference sample
and raises a flag when they stop looking alike.

The Population Stability Index (PSI) is used here because it is simple,
needs no labels, and has widely used rule-of-thumb thresholds:
    below 0.10   no meaningful change
    0.10 - 0.25  moderate change, worth a look
    above 0.25   large change, the model's results should not be trusted without review
"""

import numpy as np
import pandas as pd

NO_CHANGE, LARGE_CHANGE = 0.10, 0.25


def population_stability_index(reference: np.ndarray, current: np.ndarray, bins: int = 10) -> float:
    """How different the distribution of `current` is from `reference` (0 = identical)."""
    reference, current = np.asarray(reference, dtype=float), np.asarray(current, dtype=float)
    # Bin edges are deciles of the reference, so each reference bin holds about 10% of its values.
    edges = np.unique(np.quantile(reference, np.linspace(0, 1, bins + 1)))
    if len(edges) < 3:
        return 0.0   # the feature is constant in the reference; nothing to compare
    edges[0], edges[-1] = -np.inf, np.inf

    reference_share = np.histogram(reference, edges)[0] / len(reference)
    current_share = np.histogram(current, edges)[0] / len(current)
    # A small floor avoids dividing by zero when a bin is empty.
    reference_share, current_share = np.clip(reference_share, 1e-4, None), np.clip(current_share, 1e-4, None)
    return float(np.sum((current_share - reference_share) * np.log(current_share / reference_share)))


def drift_report(reference: pd.DataFrame, current: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """PSI for every column, with a plain-language verdict, worst first."""
    rows = []
    for column in columns:
        psi = population_stability_index(reference[column], current[column])
        verdict = "no meaningful change" if psi < NO_CHANGE else "moderate change" if psi < LARGE_CHANGE else "LARGE CHANGE"
        rows.append({"feature": column, "psi": round(psi, 4), "reference_mean": reference[column].mean(),
                     "current_mean": current[column].mean(), "verdict": verdict})
    return pd.DataFrame(rows).sort_values("psi", ascending=False).reset_index(drop=True)


def prediction_summary(log: pd.DataFrame) -> dict:
    """Summary of the predictions served, from the API's prediction log."""
    return {
        "predictions_served": int(len(log)),
        "mean_estimate": round(float(log["estimate"].mean()), 1),
        "share_near_end_of_life_percent": round(float((log["status"] == "near_end_of_predicted_life").mean() * 100), 1),
        "share_open_ended_range_percent": round(float(log["high"].isna().mean() * 100), 1),
        "status_counts": log["status"].value_counts().to_dict(),
    }
