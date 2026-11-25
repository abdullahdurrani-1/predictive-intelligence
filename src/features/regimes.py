"""Operating-regime handling for the multi-condition subsets (FD002, FD004).

In FD002 and FD004 each cycle is flown in one of six flight conditions
(combinations of altitude, Mach number and throttle). A sensor reading jumps
whenever the condition changes, and those jumps are far larger than the drift
caused by wear. The fix is to judge every reading against what is normal *for
its own flight condition*.
"""

import numpy as np
import pandas as pd

from src.data.cmapss import SETTING_COLUMNS


def assign_regime(frame: pd.DataFrame) -> pd.Series:
    """Label each row with its flight condition.

    The settings are recorded with small jitter around a few fixed values, so
    rounding them recovers the condition: altitude to the nearest thousand
    feet, Mach to two decimals, throttle to the nearest degree.
    """
    altitude = frame[SETTING_COLUMNS[0]].round(0).astype(int)
    mach = (frame[SETTING_COLUMNS[1]] * 100).round(0).astype(int)
    throttle = frame[SETTING_COLUMNS[2]].round(0).astype(int)
    return altitude.astype(str) + "/" + mach.astype(str) + "/" + throttle.astype(str)


class RegimeScaler:
    """Standardise each sensor separately within each flight condition.

    After scaling, a value of +1 means "one standard deviation above what this
    sensor normally reads in this flight condition". The statistics are learned
    from training engines only.
    """

    def fit(self, frame: pd.DataFrame, sensors: list[str]) -> "RegimeScaler":
        self.sensors = list(sensors)
        grouped = frame[self.sensors].groupby(assign_regime(frame))
        self.mean_ = grouped.mean()
        self.std_ = grouped.std(ddof=0)
        return self

    def transform(self, frame: pd.DataFrame) -> pd.DataFrame:
        regime = assign_regime(frame)
        unknown = sorted(set(regime.unique()) - set(self.mean_.index))
        if unknown:
            raise ValueError(f"Flight conditions not seen when the scaler was fitted: {unknown}")

        mean = self.mean_.loc[regime].to_numpy()
        std = self.std_.loc[regime].to_numpy()
        values = frame[self.sensors].to_numpy(dtype=float)
        # A sensor that never varies within a condition carries no information there: report 0.
        scaled = np.divide(values - mean, std, out=np.zeros_like(values), where=std > 1e-9)

        result = frame.copy()
        result[self.sensors] = scaled
        return result

    def informative_sensors(self, min_distinct: int = 3) -> list[str]:
        """Sensors that vary in at least one flight condition."""
        return [name for name in self.sensors if (self.std_[name] > 1e-9).any()]
