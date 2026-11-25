"""Upload of one engine's sensor history as a file.

Accepted layouts:
  * CSV with a header row: a `cycle` column, `sensor_1` ... `sensor_21`, and optionally `setting_1` ... `setting_3`.
  * The NASA text layout: 26 numbers per line separated by spaces, no header
    (engine number, cycle, 3 settings, 21 sensors). Such a file may hold several engines.

The browser sends the file's text; nothing is stored on disk.
"""

import io
from datetime import datetime, timezone

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse, Response
from pydantic import BaseModel, Field

from api.extra import get_service
from src.data.cmapss import COLUMN_NAMES, SENSOR_COLUMNS, SETTING_COLUMNS
from src.service.engine_service import EngineService
from src.service.report import render_report

router = APIRouter()
MAX_CHARACTERS = 5_000_000


class Upload(BaseModel):
    filename: str = Field(max_length=200)
    content: str = Field(min_length=1, max_length=MAX_CHARACTERS)
    engine_number: int | None = None      # which engine to use when the file holds several
    as_report: bool = False               # return a downloadable report instead of the on-screen result


def refuse(reasons: list[str]) -> None:
    raise HTTPException(status_code=422, detail={"refused": True, "reasons": reasons})


def parse(content: str) -> pd.DataFrame:
    """Turn the file text into a table with the dataset's column names."""
    first_line = content.lstrip().splitlines()[0].lower()
    try:
        if "cycle" in first_line:
            table = pd.read_csv(io.StringIO(content), sep=None, engine="python")
            table.columns = [str(c).strip().lower() for c in table.columns]
            if "engine_id" not in table:
                table["engine_id"] = 1
        else:
            table = pd.read_csv(io.StringIO(content), sep=r"\s+", header=None)
            if table.shape[1] != len(COLUMN_NAMES):
                refuse([f"This looks like a file without a header row, but it has {table.shape[1]} columns per line. "
                        f"The NASA layout has exactly {len(COLUMN_NAMES)}: engine number, flight number, 3 settings and 21 sensors. "
                        "Otherwise use a CSV file with a header row (download the example file to see the layout)."])
            table.columns = COLUMN_NAMES
    except HTTPException:
        raise
    except Exception:
        refuse(["The file could not be read as a table. Use a CSV file with a header row, or the NASA text layout."])

    missing = [name for name in ["cycle", *SENSOR_COLUMNS] if name not in table.columns]
    if missing:
        refuse([f"These columns are missing: {', '.join(missing)}. The file needs a 'cycle' column and sensor_1 to sensor_21."])
    for name in SETTING_COLUMNS:           # settings are optional; assume the training condition if absent
        if name not in table.columns:
            table[name] = 100.0 if name == "setting_3" else 0.0

    numeric = table[COLUMN_NAMES].apply(pd.to_numeric, errors="coerce")
    bad = numeric.columns[numeric.isna().any()].tolist()
    if bad:
        refuse([f"Some values are empty or are not numbers, in: {', '.join(bad[:6])}. Every reading must be a number."])
    return numeric


@router.get("/uploads/example", response_class=PlainTextResponse)
def example_file(service: EngineService = Depends(get_service)) -> str:
    """A correctly laid-out file (the recorded history of demonstration engine 37)."""
    return service.history(37)[["cycle", *SETTING_COLUMNS, *SENSOR_COLUMNS]].to_csv(index=False)


@router.get("/engines/{engine_id}/report")
def engine_report_download(engine_id: int, cycle: int | None = None, service: EngineService = Depends(get_service)) -> Response:
    """A downloadable PDF report for a demonstration engine, as of `cycle` (default: its last recorded flight)."""
    try:
        facts = service.report(engine_id, cycle)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"No engine with id {engine_id}") from None
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from None
    estimates = service.trajectory(engine_id)
    estimates = estimates[estimates["cycle"] <= facts["cycles_recorded"]]
    pdf = render_report(facts, estimates, "NASA C-MAPSS FD001 demonstration engine")
    name = f"engine_{engine_id}_report_flight_{facts['cycles_recorded']}.pdf"
    return Response(pdf, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{name}"'})


@router.post("/uploads", response_model=None)
def upload_engine(body: Upload, service: EngineService = Depends(get_service)):
    table = parse(body.content)

    engines = sorted(int(e) for e in table["engine_id"].unique())
    if len(engines) > 1 and body.engine_number is None:
        return {"needs_engine_choice": True, "engines": engines,
                "message": f"This file contains {len(engines)} engines. Choose which one to assess."}
    chosen = body.engine_number if body.engine_number is not None else engines[0]
    if chosen not in engines:
        refuse([f"Engine {chosen} is not in this file."])

    history = table[table["engine_id"] == chosen].sort_values("cycle").reset_index(drop=True)
    cycles = history["cycle"].astype(int).tolist()
    if cycles != list(range(1, len(cycles) + 1)):
        refuse(["The flights must be numbered 1, 2, 3 and so on with none missing or repeated. "
                f"This file has {len(cycles)} rows, numbered from {min(cycles)} to {max(cycles)}. "
                "The model needs the engine's complete record from its first flight."])
    history["cycle"] = cycles

    findings = service.validator.check(history)
    if not findings.accepted:
        refuse(findings.problems)

    label = f"Uploaded engine ({body.filename}" + (f", engine {chosen})" if len(engines) > 1 else ")")
    facts = service.assess(history, engine_label=label)
    facts.update(engine_id=0, last_recorded_cycle=len(history), is_latest_cycle=True,
                 analysed_at=datetime.now(timezone.utc).isoformat(timespec="seconds"))
    estimates = service.predict_rows(service._featured(history))
    if body.as_report:
        pdf = render_report(facts, estimates[estimates["cycle"] >= 31], f"from uploaded file {body.filename}")
        return Response(pdf, media_type="application/pdf",
                        headers={"Content-Disposition": 'attachment; filename="engine_report_uploaded.pdf"'})
    return {
        "needs_engine_choice": False, "facts": facts,
        "history": {"sensors": history[["cycle", *SENSOR_COLUMNS]].to_dict(orient="list"),
                    "estimates": estimates[estimates["cycle"] >= 31].round(2).to_dict(orient="list")},
        "file": {"name": body.filename, "flights": len(history), "engines_in_file": len(engines), "engine_used": chosen},
    }
