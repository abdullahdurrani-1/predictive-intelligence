"""SHAP-based explanations for the tabular RUL model.

SHAP splits one prediction into a starting point (the model's average
prediction) plus one contribution per feature. The contributions add up
exactly to the prediction, so they can be read as "this feature moved the
estimate by so many cycles".

These explain what the *model* did. They do not show what is physically wrong
with an engine, and a large contribution is not proof of cause.
"""

import numpy as np
import pandas as pd
import shap

from src.data.cmapss import SENSOR_INFO


def sensor_of(feature: str) -> str:
    """'sensor_11_mean30' -> 'sensor_11'."""
    return "_".join(feature.split("_")[:2])


def kind_of(feature: str) -> str:
    """Which kind of feature this is: current reading, recent average, recent variability, or change from baseline."""
    if feature.endswith("_delta"):
        return "change from baseline"
    if "_mean" in feature:
        return "recent average"
    if "_std" in feature:
        return "recent variability"
    return "current reading"


def explain(model, rows: pd.DataFrame) -> tuple[pd.DataFrame, float]:
    """Return (contributions in cycles, one column per feature; the model's average prediction)."""
    explainer = shap.TreeExplainer(model)
    contributions = pd.DataFrame(explainer.shap_values(rows), index=rows.index, columns=rows.columns)
    return contributions, float(np.ravel(explainer.expected_value)[0])


def by_sensor(contributions: pd.DataFrame) -> pd.DataFrame:
    """Add up each sensor's features, giving one signed contribution per sensor."""
    return contributions.T.groupby(sensor_of).sum().T


def top_reasons(contribution_row: pd.Series, count: int = 5) -> list[dict]:
    """The sensors that moved one prediction the most, as plain records for the assistant."""
    per_sensor = contribution_row.groupby(sensor_of).sum()
    strongest = per_sensor.reindex(per_sensor.abs().sort_values(ascending=False).index).head(count)
    return [
        {
            "sensor": name,
            "symbol": SENSOR_INFO[name][0],
            "description": SENSOR_INFO[name][1],
            "cycles": round(float(value), 1),
            "effect": "lowers the estimate" if value < 0 else "raises the estimate",
        }
        for name, value in strongest.items()
    ]
