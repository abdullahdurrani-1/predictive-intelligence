"""Monitoring report: has the incoming data drifted, and what is the model predicting?

Run from the project root:
    python scripts/monitor_report.py                 # healthy case: test engines against training engines
    python scripts/monitor_report.py --inject-drift  # demonstration: a sensor fault is added to the incoming data

Reference data: the FD001 training engines the model learned from.
Incoming data: by default the FD001 test engines, standing in for "this week's readings".
Only early-life readings (first 30 flights) are compared, because later readings
differ for a legitimate reason: engines at different stages of wear.

Writes monitoring/drift_report.csv and monitoring/monitoring_summary.json.
Exit code 1 means a large change was found, so a scheduler or CI job can alert on it.
"""

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src import config  # noqa: E402
from src.data.cmapss import load_subset  # noqa: E402
from src.monitoring.drift import LARGE_CHANGE, drift_report, prediction_summary  # noqa: E402

EARLY_LIFE_FLIGHTS = 30


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--inject-drift", action="store_true",
                        help="shift sensor 11 in the incoming data by one training standard deviation")
    arguments = parser.parse_args()

    train, test, _ = load_subset("FD001")
    reference = train[train["cycle"] <= EARLY_LIFE_FLIGHTS]
    incoming = test[test["cycle"] <= EARLY_LIFE_FLIGHTS].copy()
    if arguments.inject_drift:
        incoming["sensor_11"] += reference["sensor_11"].std()

    report = drift_report(reference, incoming, config.FD001_SENSORS)
    output_dir = ROOT / "monitoring"
    output_dir.mkdir(exist_ok=True)
    report.to_csv(output_dir / "drift_report.csv", index=False)

    summary = {
        "reference_rows": len(reference), "incoming_rows": len(incoming), "drift_injected": arguments.inject_drift,
        "features_checked": len(report), "largest_psi": float(report["psi"].max()),
        "features_with_large_change": report.loc[report["psi"] >= LARGE_CHANGE, "feature"].tolist(),
        "features_with_moderate_change": report.loc[report["verdict"] == "moderate change", "feature"].tolist(),
    }
    log_path = output_dir / "prediction_log.jsonl"
    if log_path.exists():
        summary["predictions"] = prediction_summary(pd.read_json(log_path, lines=True))
    (output_dir / "monitoring_summary.json").write_text(json.dumps(summary, indent=1))

    print(report.round(4).to_string(index=False))
    print()
    print(json.dumps(summary, indent=1))
    if summary["features_with_large_change"]:
        print("\nALERT: large change in incoming data. Predictions should be reviewed before they are relied on.")
        raise SystemExit(1)
    print("\nNo large change in incoming data.")


if __name__ == "__main__":
    main()
