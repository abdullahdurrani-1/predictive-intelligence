"""Simulate new engine readings arriving one flight at a time.

Replays a test engine's recorded history through the running API as if each
flight had just landed, and prints how the estimate changes. Start the API
first (uvicorn api.main:app), then from the project root:

    python scripts/simulate_stream.py --engine 37 --every 10

With --drift a slow fault is injected into one sensor so that the monitoring
report (scripts/monitor_report.py) has something to detect.
"""

import argparse
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src import config  # noqa: E402
from src.data.cmapss import load_subset  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--engine", type=int, default=37)
    parser.add_argument("--every", type=int, default=10, help="send an assessment request every N flights")
    parser.add_argument("--api", default="http://127.0.0.1:8000")
    parser.add_argument("--drift", action="store_true", help="add a growing offset to sensor 2 (simulated sensor fault)")
    arguments = parser.parse_args()

    _, test, _ = load_subset("FD001")
    history = test[test["engine_id"] == arguments.engine].reset_index(drop=True)
    if history.empty:
        raise SystemExit(f"No engine {arguments.engine} in the FD001 test set")
    if arguments.drift:
        history["sensor_2"] = history["sensor_2"] + 0.02 * history["cycle"]

    readings = []
    print(f"Replaying engine {arguments.engine}: {len(history)} flights" + (" with injected sensor drift" if arguments.drift else ""))
    print(f"{'flight':>7} {'estimate':>9} {'range':>14}  status")
    for _, row in history.iterrows():
        readings.append({"cycle": int(row["cycle"]), "setting_1": float(row["setting_1"]),
                         "setting_2": float(row["setting_2"]), "setting_3": float(row["setting_3"]),
                         "sensors": {name: float(row[name]) for name in config.FD001_SENSORS}})
        is_last = int(row["cycle"]) == len(history)
        if int(row["cycle"]) < 31 or (int(row["cycle"]) % arguments.every and not is_last):
            continue
        label = f"Engine {arguments.engine}" + (" (drift test)" if arguments.drift else " (stream)")
        response = httpx.post(f"{arguments.api}/assess", json={"engine_label": label, "readings": readings}, timeout=60)
        response.raise_for_status()
        facts = response.json()
        high = "or more" if facts["range_is_open_ended"] else f"to {facts['range_high_cycles']}"
        print(f"{facts['cycles_recorded']:>7} {facts['estimate_cycles']:>9} {str(facts['range_low_cycles']) + ' ' + high:>14}  {facts['status']['label']}")


if __name__ == "__main__":
    main()
