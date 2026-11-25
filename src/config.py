"""Project-wide settings decided in Phase 4.

Each value is justified in notebooks/04_feature_engineering.ipynb and logged
in docs/DECISIONS.md. Change them there first, then here.
"""

RANDOM_SEED = 42

# Sensors that vary in FD001. Sensors 1, 5, 10, 16, 18, 19 are constant and
# sensor 6 takes two values one rounding step apart.
FD001_SENSORS = [
    "sensor_2", "sensor_3", "sensor_4", "sensor_7", "sensor_8", "sensor_9", "sensor_11",
    "sensor_12", "sensor_13", "sensor_14", "sensor_15", "sensor_17", "sensor_20", "sensor_21",
]

RUL_CAP = 125            # D-008: labels above this are treated as "healthy"
ROLLING_WINDOW = 30      # D-009: cycles in the rolling mean / standard deviation
BASELINE_CYCLES = 20     # D-009: early-life cycles that define an engine's own baseline
SEQUENCE_WINDOW = 30     # D-011: cycles per input window for sequence models
VALIDATION_FRACTION = 0.2
