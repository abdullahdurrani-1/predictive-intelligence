"""Evaluation metrics for RUL prediction.

All three metrics take the error as  predicted - true:
negative = the model predicted failure too early (cautious),
positive = the model predicted failure too late (the dangerous direction).
"""

import numpy as np


def rmse(true_rul, predicted_rul) -> float:
    """Root mean squared error, in cycles. Large errors count disproportionately."""
    error = np.asarray(predicted_rul, dtype=float) - np.asarray(true_rul, dtype=float)
    return float(np.sqrt(np.mean(error**2)))


def mae(true_rul, predicted_rul) -> float:
    """Mean absolute error, in cycles: the typical size of a miss."""
    error = np.asarray(predicted_rul, dtype=float) - np.asarray(true_rul, dtype=float)
    return float(np.mean(np.abs(error)))


def nasa_score(true_rul, predicted_rul, early_scale: float = 13.0, late_scale: float = 10.0) -> float:
    """Asymmetric PHM08 score, summed over engines. Lower is better; 0 is perfect.

    Each engine contributes exp(-d/early_scale) - 1 if the prediction is early
    (d < 0) and exp(d/late_scale) - 1 if it is late (d >= 0). With the default
    scales a late prediction costs more than an equally large early one, which
    is the behaviour Saxena et al. (2008) describe in words.

    The paper prints "a1 = 10, a2 = 13" and says late predictions are penalised
    more heavily; only 13 for early and 10 for late does that, which is also the
    form used throughout the RUL literature (docs/DECISIONS.md, D-020).

    Because it is a sum, the score grows with the number of engines and is
    dominated by the few worst late predictions. Compare it only between
    models evaluated on the same engines.
    """
    error = np.asarray(predicted_rul, dtype=float) - np.asarray(true_rul, dtype=float)
    penalty = np.where(error < 0, np.exp(-error / early_scale) - 1, np.exp(error / late_scale) - 1)
    return float(np.sum(penalty))
