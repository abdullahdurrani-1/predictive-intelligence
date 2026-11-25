"""Checks on incoming sensor data before the model is allowed to answer.

The model only understands engines like the ones it was trained on: the NASA
C-MAPSS FD001 simulated turbofan, flown at one condition, with readings in
that dataset's units. Given anything else it would still produce a number,
and that number would be meaningless. These checks exist to stop that.

Two kinds of finding:
  problems  -> the data is refused and no estimate is given
  warnings  -> an estimate is given, with the concern shown beside it
"""

from dataclasses import dataclass, field

import pandas as pd

from src.data.cmapss import SENSOR_COLUMNS, SENSOR_INFO, SETTING_COLUMNS

RANGE_MARGIN = 0.5        # how far beyond the training range a sensor's typical value may sit, as a share of that range
FROZEN_WINDOW = 30        # flights examined for a sensor that has stopped moving
FROZEN_SHARE = 0.15       # "stopped moving" = recent spread below this share of normal healthy noise


@dataclass
class Findings:
    problems: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def accepted(self) -> bool:
        return not self.problems


def describe(sensor: str) -> str:
    symbol, description, unit = SENSOR_INFO[sensor]
    return f"sensor {sensor.split('_')[1]} ({description}, {symbol})"


class DataValidator:
    """Learns what normal readings look like from the training engines, then checks new data against it."""

    def __init__(self, training: pd.DataFrame, model_sensors: list[str]):
        self.model_sensors = model_sensors
        self.low = training[SENSOR_COLUMNS].min()
        self.high = training[SENSOR_COLUMNS].max()
        self.setting_low = training[SETTING_COLUMNS].min()
        self.setting_high = training[SETTING_COLUMNS].max()
        # Normal flight-to-flight flicker of each sensor on a healthy engine.
        early = training[training["cycle"] <= 30]
        self.healthy_noise = (early[SENSOR_COLUMNS] - early.groupby("engine_id")[SENSOR_COLUMNS].transform("mean")).std()

    def check(self, history: pd.DataFrame) -> Findings:
        findings = Findings()

        # 1. Flight condition. The model was trained at one condition only (sea level, full throttle setting).
        for setting in SETTING_COLUMNS:
            if setting not in history:
                continue
            span = max(float(self.setting_high[setting] - self.setting_low[setting]), 0.01)
            typical = float(history[setting].median())
            if not self.setting_low[setting] - span <= typical <= self.setting_high[setting] + span:
                findings.problems.append(
                    f"Flight setting {setting.split('_')[1]} is typically {typical:g}, but this model only covers engines "
                    f"flown at the single condition it was trained on ({self.setting_low[setting]:g} to {self.setting_high[setting]:g}).")

        # 2. Plausible values. A sensor whose typical reading is far outside anything seen in
        #    training means different units or a different kind of engine.
        out_of_range = []
        for sensor in SENSOR_COLUMNS:
            # A caller may send only the sensors the model uses; one that was not sent cannot be checked.
            if sensor not in history or history[sensor].isna().all():
                continue
            span = float(self.high[sensor] - self.low[sensor])
            margin = span * RANGE_MARGIN if span > 0 else max(abs(float(self.high[sensor])) * 0.01, 0.01)
            typical = float(history[sensor].median())
            if not self.low[sensor] - margin <= typical <= self.high[sensor] + margin:
                out_of_range.append(f"{describe(sensor)} is typically {typical:.4g} {SENSOR_INFO[sensor][2]}; "
                                    f"the model has only seen {self.low[sensor]:.4g} to {self.high[sensor]:.4g}")
        if out_of_range:
            shown = "; ".join(out_of_range[:4]) + (f"; and {len(out_of_range) - 4} more" if len(out_of_range) > 4 else "")
            findings.problems.append(
                f"{len(out_of_range)} of the sensors read far outside what this model was trained on ({shown}). "
                "This usually means different units or a different type of engine. No estimate is given, "
                "because it would not mean anything.")

        # 3. A sensor that has stopped moving. A frozen sensor reports "no wear" and makes the estimate too optimistic.
        if len(history) >= FROZEN_WINDOW:
            recent = history.tail(FROZEN_WINDOW)
            for sensor in self.model_sensors:
                if recent[sensor].std() < FROZEN_SHARE * self.healthy_noise[sensor]:
                    findings.warnings.append(
                        f"S{describe(sensor)[1:]} has barely changed over the last {FROZEN_WINDOW} flights. "
                        "A sensor stuck on one value makes the engine look healthier than it is. "
                        "Check that this sensor is working before relying on the estimate.")

        # 4. Isolated readings far outside the training range (spikes, drop-outs).
        for sensor in self.model_sensors:
            span = float(self.high[sensor] - self.low[sensor])
            outside = ((history[sensor] < self.low[sensor] - span) | (history[sensor] > self.high[sensor] + span)).sum()
            if 0 < outside and not out_of_range:
                findings.warnings.append(f"S{describe(sensor)[1:]} has {int(outside)} reading(s) far outside the normal range. "
                                         "These may be sensor glitches and can distort the estimate.")
        return findings
