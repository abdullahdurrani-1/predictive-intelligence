"""HTTP API for the Predictive Intelligence demonstration.

Run from the project root:
    uvicorn api.main:app --reload
Interactive documentation is then served at http://127.0.0.1:8000/docs
"""

import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from pydantic import BaseModel, Field

from src.assistant.assistant import answer_question
from src.assistant.knowledge import SAFETY_NOTE
from src.data.cmapss import COLUMN_NAMES, SENSOR_COLUMNS, SENSOR_INFO, SENSOR_STATION, STATION_NAMES
from src.service.engine_service import EngineService



def load_env_file() -> None:
    """Read KEY=value lines from a .env file in the project root, without overriding real environment variables.

    This is where an API key for the assistant goes. The file is excluded from Git.
    """
    env_file = Path(__file__).resolve().parents[1] / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"'))


load_env_file()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("predictive_intelligence.api")

app = FastAPI(
    title="Predictive Intelligence API",
    version="0.1.0",
    description="Remaining-useful-life estimates, ranges, explanations and plain-language answers for "
                "engines in the NASA C-MAPSS FD001 benchmark. Research demonstration on simulated data.",
)


from api import extra  # noqa: E402

# One service instance shared by every route.
get_service = extra.get_service
app.include_router(extra.router)

from api import uploads  # noqa: E402

app.include_router(uploads.router)


def prediction_log_path() -> Path:
    path = get_service().root / "monitoring" / "prediction_log.jsonl"
    path.parent.mkdir(exist_ok=True)
    return path


def log_prediction(source: str, facts: dict) -> None:
    """Append one line per prediction served, for the monitoring report."""
    record = {
        "time": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": source, "engine": facts["engine"], "cycles_recorded": facts["cycles_recorded"],
        "estimate": facts["estimate_cycles"], "low": facts["range_low_cycles"],
        "high": facts["range_high_cycles"], "status": facts["status"]["key"],
    }
    with prediction_log_path().open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record) + "\n")


@app.middleware("http")
async def log_requests(request: Request, call_next):
    started = time.perf_counter()
    response = await call_next(request)
    logger.info("%s %s -> %s in %.0f ms", request.method, request.url.path, response.status_code,
                (time.perf_counter() - started) * 1000)
    return response


class Question(BaseModel):
    question: str = Field(min_length=1, max_length=500, examples=["Is this engine healthy?"])
    use_language_model: bool = True


class Reading(BaseModel):
    """One cycle of raw readings for one engine, using the dataset's column names."""
    cycle: int = Field(ge=1)
    setting_1: float = 0.0
    setting_2: float = 0.0
    setting_3: float = 100.0
    sensors: dict[str, float] = Field(description="sensor_1 ... sensor_21")


class History(BaseModel):
    engine_label: str = "submitted engine"
    readings: list[Reading] = Field(min_length=1)


def report_or_404(engine_id: int, service: EngineService, cycle: int | None = None) -> dict:
    try:
        return service.report(engine_id, cycle)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"No engine with id {engine_id}") from None
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from None


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/model")
def model_information(service: EngineService = Depends(get_service)) -> dict:
    return {
        "model": "XGBoost on engineered sensor features",
        "trained_on": "NASA C-MAPSS FD001 training set (100 simulated engines)",
        "rul_cap_cycles": service.cap,
        "range": {"method": "conformalized quantile regression",
                  "target_coverage_percent": round(service.settings["target_coverage"] * 100),
                  "measured_test_coverage_percent": service.settings["test_coverage_capped_truth_percent"],
                  "average_width_cycles": service.settings["test_average_width_cycles"]},
        "typical_error_cycles": service._typical_error(),
        "sensors_used": {name: SENSOR_INFO[name][1] for name in service.sensors},
        "notice": SAFETY_NOTE,
    }


@app.get("/engines")
def list_engines(service: EngineService = Depends(get_service)) -> dict:
    return {"engines": service.engine_ids()}


@app.get("/datasets")
def datasets(service: EngineService = Depends(get_service)) -> dict:
    """The four benchmark subsets. Only FD001 has a model served by this application."""
    described = {
        "FD001": ("1 flight condition, 1 fault mode", True),
        "FD002": ("6 flight conditions, 1 fault mode", False),
        "FD003": ("1 flight condition, 2 fault modes", False),
        "FD004": ("6 flight conditions, 2 fault modes", False),
    }
    results_path = service.root / "experiments" / "all_subsets_xgboost.csv"
    results = pd.read_csv(results_path, index_col="subset") if results_path.exists() else None
    items = []
    for name, (description, served) in described.items():
        item = {"name": name, "description": description, "served": served,
                "availability": "Engines can be explored" if served
                else "Research results only; no model is served for this subset",
                "test_engines": None, "cv_rmse": None, "test_rmse_truth_capped": None}
        if results is not None and name in results.index:
            item.update(test_engines=int(results.loc[name, "test engines"]),
                        cv_rmse=round(float(results.loc[name, "CV RMSE"]), 1),
                        test_rmse_truth_capped=round(float(results.loc[name, "test RMSE (truth capped)"]), 1))
        items.append(item)
    return {"datasets": items, "source": "NASA C-MAPSS simulated benchmark data"}


@app.get("/fleet")
def fleet(service: EngineService = Depends(get_service)) -> dict:
    return {"dataset": "FD001", "engines": service.fleet_summary}


@app.get("/sensors")
def sensors(service: EngineService = Depends(get_service)) -> dict:
    """All 21 recorded sensors, and which of them the model uses."""
    items = []
    for name in SENSOR_COLUMNS:
        symbol, description, unit = SENSOR_INFO[name]
        station = SENSOR_STATION.get(name)
        items.append({"name": name, "number": int(name.split("_")[1]), "symbol": symbol, "description": description,
                      "unit": unit, "station": station, "station_name": STATION_NAMES.get(station),
                      "used_by_model": name in service.sensors,
                      "note": None if name in service.sensors else "Does not vary in FD001, so the model does not use it"})
    return {"sensors": items,
            "naming_note": "The dataset only numbers its sensors. Names follow the order of Table 2 in Saxena et al. (2008)."}


@app.get("/engines/{engine_id}")
def engine_report(engine_id: int, cycle: int | None = Query(default=None, ge=1),
                  service: EngineService = Depends(get_service)) -> dict:
    facts = report_or_404(engine_id, service, cycle)
    facts["analysed_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    if cycle is None:
        log_prediction("engine_report", facts)
    return facts


@app.get("/engines/{engine_id}/history")
def engine_history(engine_id: int, service: EngineService = Depends(get_service)) -> dict:
    try:
        history = service.history(engine_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"No engine with id {engine_id}") from None
    return {"engine_id": engine_id, "sensors": history[["cycle", *SENSOR_COLUMNS]].to_dict(orient="list"),
            "estimates": service.trajectory(engine_id).round(2).to_dict(orient="list"),
            "benchmark_label": {
                "cycle": int(history["cycle"].max()), "true_rul": service.benchmark_true_rul(engine_id),
                "note": "True remaining life at the last recorded flight, from the benchmark answer file. "
                        "Known only because this is a finished simulation."}}


@app.post("/engines/{engine_id}/ask")
def ask_about_engine(engine_id: int, body: Question, service: EngineService = Depends(get_service)) -> dict:
    facts = report_or_404(engine_id, service)
    reply = answer_question(body.question, facts, use_language_model=body.use_language_model)
    return {"engine_id": engine_id, "question": body.question, **reply}


@app.post("/assess")
def assess_submitted_history(body: History, service: EngineService = Depends(get_service)) -> dict:
    """Assess an engine from readings sent by the caller (used by the streaming simulation)."""
    rows = []
    for reading in body.readings:
        missing = [name for name in service.sensors if name not in reading.sensors]
        if missing:
            raise HTTPException(status_code=422, detail=f"Cycle {reading.cycle} is missing sensors: {missing}")
        rows.append({"engine_id": 0, "cycle": reading.cycle, "setting_1": reading.setting_1,
                     "setting_2": reading.setting_2, "setting_3": reading.setting_3, **reading.sensors})
    history = pd.DataFrame(rows).reindex(columns=COLUMN_NAMES)

    cycles = history["cycle"].tolist()
    if cycles != list(range(1, len(cycles) + 1)):
        raise HTTPException(status_code=422, detail="Cycles must start at 1 and increase by 1 with no gaps.")

    findings = service.validator.check(history)
    if not findings.accepted:
        raise HTTPException(status_code=422, detail={"refused": True, "reasons": findings.problems})

    facts = service.assess(history, engine_label=body.engine_label)
    log_prediction("assess", facts)
    return facts
