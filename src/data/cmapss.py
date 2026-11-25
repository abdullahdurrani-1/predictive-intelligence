"""Loading helpers for the NASA C-MAPSS turbofan text files.

The raw files have no header row, so the column names are defined here once
and reused by every notebook and script.
"""

from pathlib import Path

import pandas as pd

INDEX_COLUMNS = ["engine_id", "cycle"]
SETTING_COLUMNS = ["setting_1", "setting_2", "setting_3"]
SENSOR_COLUMNS = [f"sensor_{number}" for number in range(1, 22)]
COLUMN_NAMES = INDEX_COLUMNS + SETTING_COLUMNS + SENSOR_COLUMNS

# The dataset README only numbers the sensors. These names follow the order of
# Table 2 in Saxena et al. (2008), which is the convention used in the RUL
# literature. Treat them as an informed mapping, not something the files state.
SENSOR_INFO = {
    "sensor_1": ("T2", "Total temperature at fan inlet", "°R"),
    "sensor_2": ("T24", "Total temperature at LPC outlet", "°R"),
    "sensor_3": ("T30", "Total temperature at HPC outlet", "°R"),
    "sensor_4": ("T50", "Total temperature at LPT outlet", "°R"),
    "sensor_5": ("P2", "Pressure at fan inlet", "psia"),
    "sensor_6": ("P15", "Total pressure in bypass duct", "psia"),
    "sensor_7": ("P30", "Total pressure at HPC outlet", "psia"),
    "sensor_8": ("Nf", "Physical fan speed", "rpm"),
    "sensor_9": ("Nc", "Physical core speed", "rpm"),
    "sensor_10": ("epr", "Engine pressure ratio (P50/P2)", "-"),
    "sensor_11": ("Ps30", "Static pressure at HPC outlet", "psia"),
    "sensor_12": ("phi", "Ratio of fuel flow to Ps30", "pps/psi"),
    "sensor_13": ("NRf", "Corrected fan speed", "rpm"),
    "sensor_14": ("NRc", "Corrected core speed", "rpm"),
    "sensor_15": ("BPR", "Bypass ratio", "-"),
    "sensor_16": ("farB", "Burner fuel-air ratio", "-"),
    "sensor_17": ("htBleed", "Bleed enthalpy", "-"),
    "sensor_18": ("Nf_dmd", "Demanded fan speed", "rpm"),
    "sensor_19": ("PCNfR_dmd", "Demanded corrected fan speed", "rpm"),
    "sensor_20": ("W31", "HPT coolant bleed", "lbm/s"),
    "sensor_21": ("W32", "LPT coolant bleed", "lbm/s"),
}

# Where each sensor's quantity is measured, using the station numbers that
# appear in the sensor symbols themselves (T2, P15, T24, T30, T50). Quantities
# with no station in their name (shaft speeds, ratios, bleeds) have none.
SENSOR_STATION = {
    "sensor_1": "2", "sensor_5": "2",
    "sensor_6": "15",
    "sensor_2": "24",
    "sensor_3": "30", "sensor_7": "30", "sensor_11": "30",
    "sensor_4": "50",
}
STATION_NAMES = {
    "2": "Fan inlet", "15": "Bypass duct", "24": "LPC outlet", "30": "HPC outlet", "50": "LPT outlet",
}


def find_project_root(start: Path | None = None) -> Path:
    """Walk upwards from `start` until the folder containing data/raw is found."""
    current = (start or Path.cwd()).resolve()
    for folder in [current, *current.parents]:
        if (folder / "data" / "raw").is_dir():
            return folder
    raise FileNotFoundError("Could not find a parent folder containing data/raw")


def read_sensor_file(path: Path) -> pd.DataFrame:
    """Read one train or test file into a DataFrame with named columns."""
    # Rows end with trailing spaces, so a regex separator is needed;
    # a plain single-space separator would create empty extra columns.
    frame = pd.read_csv(path, sep=r"\s+", header=None, names=COLUMN_NAMES)
    frame["engine_id"] = frame["engine_id"].astype(int)
    frame["cycle"] = frame["cycle"].astype(int)
    # A few sensors are recorded as whole numbers. Store every measurement as a
    # float so that later steps (scaling, replacing values) treat all sensors alike.
    measurement_columns = SETTING_COLUMNS + SENSOR_COLUMNS
    frame[measurement_columns] = frame[measurement_columns].astype(float)
    return frame


def load_subset(
    subset: str = "FD001", raw_dir: Path | None = None
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Load the train table, the test table, and the test RUL labels of one subset.

    The RUL table has one row per test engine: the true number of cycles that
    engine still had left after its last recorded cycle.
    """
    raw_dir = raw_dir or find_project_root() / "data" / "raw"
    train = read_sensor_file(raw_dir / f"train_{subset}.txt")
    test = read_sensor_file(raw_dir / f"test_{subset}.txt")

    rul = pd.read_csv(raw_dir / f"RUL_{subset}.txt", sep=r"\s+", header=None, names=["true_rul"])
    # Line 1 of the RUL file belongs to test engine 1, line 2 to engine 2, and so on.
    rul.insert(0, "engine_id", range(1, len(rul) + 1))
    return train, test, rul


def add_training_rul(train: pd.DataFrame) -> pd.DataFrame:
    """Return a copy of the training table with a `rul` column.

    Training engines are recorded until they fail, so the last cycle of each
    engine is its failure point and RUL = last cycle - current cycle.
    This is only valid for training data: test engines stop before failure.
    """
    labelled = train.copy()
    last_cycle = labelled.groupby("engine_id")["cycle"].transform("max")
    labelled["rul"] = last_cycle - labelled["cycle"]
    return labelled
