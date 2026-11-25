"""Write a PDF test report: the served model on NASA's official FD001 test set.

The 100 test engines were never used for training, tuning or calibration.
Their true remaining life comes from NASA's answer file (RUL_FD001.txt), so
every number in the report can be re-derived from the raw files.

    python scripts/test_report.py            # writes reports/FD001_test_report.pdf
"""

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from reportlab.graphics.shapes import Circle, Drawing, Line, String
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.evaluation.metrics import mae, nasa_score, rmse  # noqa: E402
from src.service.engine_service import EngineService  # noqa: E402
from src.service.report import BODY, BURGUNDY, CELL, HEADING, LINE, MUTED, ORANGE, PAGE_WIDTH, SMALL, TITLE, boxed  # noqa: E402

GOOD = colors.HexColor("#2f8f5b")
BAD = colors.HexColor("#c0392b")


def test_results(service: EngineService) -> pd.DataFrame:
    """One row per test engine: estimate and range at its last recorded flight, and the true answer."""
    latest = service._featured(service._fleet).groupby("engine_id").tail(1)
    predicted = service.predict_rows(latest)
    table = pd.DataFrame({"engine": latest["engine_id"].to_numpy(), "flights": predicted["cycle"].to_numpy(),
                          "estimate": predicted["estimate"].to_numpy(), "low": predicted["low"].to_numpy(),
                          "high": predicted["high"].to_numpy()})
    table["true_rul"] = [service.benchmark_true_rul(int(e)) for e in table["engine"]]
    table["true_capped"] = table["true_rul"].clip(upper=service.cap)
    table["error"] = table["estimate"] - table["true_rul"]
    # Exact (unrounded) range, as in notebook 09 and the paper. The table prints it to one decimal for the same reason.
    table["inside"] = (table["true_capped"] >= table["low"]) & (table["true_capped"] <= table["high"])
    return table


def scatter(table: pd.DataFrame, cap: int) -> Drawing:
    """True remaining life against the estimate, one dot per engine, with each engine's range."""
    size, left, bottom, pad = PAGE_WIDTH * 0.4, 34, 30, 8
    top = 150
    drawing = Drawing(PAGE_WIDTH, size)

    def scale(value: float, origin: float) -> float:
        return origin + min(max(value, 0), top) / top * (size - origin - pad)

    for value in range(0, top + 1, 25):
        drawing.add(Line(left, scale(value, bottom), size, scale(value, bottom), strokeColor=colors.HexColor("#e3e7ec"), strokeWidth=0.5))
        drawing.add(String(left - 5, scale(value, bottom) - 3, str(value), fontSize=7.5, fillColor=MUTED, textAnchor="end"))
        drawing.add(String(scale(value, left), bottom - 12, str(value), fontSize=7.5, fillColor=MUTED, textAnchor="middle"))
    drawing.add(Line(scale(0, left), scale(0, bottom), scale(top, left), scale(top, bottom), strokeColor=colors.HexColor("#9aa5b1"),
                     strokeWidth=0.8, strokeDashArray=[4, 3]))
    for row in table.itertuples():
        x = scale(row.true_rul, left)
        colour = GOOD if row.inside else BAD
        drawing.add(Line(x, scale(row.low, bottom), x, scale(row.high, bottom), strokeColor=colors.Color(0.85, 0.47, 0.34, alpha=0.35), strokeWidth=1.2))
        drawing.add(Circle(x, scale(row.estimate, bottom), 2.2, fillColor=colour, strokeColor=None))
    drawing.add(String((left + size) / 2, 2, "True flights remaining (NASA answer file)", fontSize=8, fillColor=MUTED, textAnchor="middle"))
    drawing.add(String(size + 10, size - 20, "Dot: estimate", fontSize=8, fillColor=MUTED))
    drawing.add(String(size + 10, size - 32, "Bar: 90% range", fontSize=8, fillColor=ORANGE))
    drawing.add(String(size + 10, size - 44, "Green: truth inside range", fontSize=8, fillColor=GOOD))
    drawing.add(String(size + 10, size - 56, "Red: truth outside range", fontSize=8, fillColor=BAD))
    drawing.add(String(size + 10, size - 68, "Dashed: perfect estimate", fontSize=8, fillColor=MUTED))
    drawing.add(String(size + 10, size - 86, "Vertical axis: estimate,", fontSize=8, fillColor=MUTED))
    drawing.add(String(size + 10, size - 98, f"capped at {cap} flights", fontSize=8, fillColor=MUTED))
    return drawing


def styled(rows, widths, header=True) -> Table:
    table = Table(rows, colWidths=widths, repeatRows=1 if header else 0)
    table.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, -1), 0.5, LINE), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                               ("LEFTPADDING", (0, 0), (-1, -1), 4), ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
    return table


def build_pdf(table: pd.DataFrame, service: EngineService, path: Path) -> dict:
    truth, estimate = table["true_rul"], table["estimate"]
    near = table[table["true_rul"] <= 30]
    figures = {
        "RMSE": rmse(truth, estimate), "MAE": mae(truth, estimate), "NASA score": nasa_score(truth, estimate),
        "RMSE, truth capped": rmse(table["true_capped"], estimate),
        "coverage": 100 * table["inside"].mean(), "width": float((table["high"] - table["low"]).mean()),
        "late": int((table["error"] > 0).sum()), "late20": int((table["error"] > 20).sum()),
        "below": int((table["true_capped"] < table["low"]).sum()), "above": int((table["true_capped"] > table["high"]).sum()),
        "near_n": len(near), "near_mae": mae(near["true_rul"], near["estimate"]),
        "near_alarm": int(((table["true_rul"] > 60) & (table["estimate"] <= 30)).sum()),
    }
    generated = datetime.now(timezone.utc).strftime("%d %B %Y, %H:%M UTC")
    story = [
        Paragraph("Model test report: NASA C-MAPSS FD001", TITLE),
        Paragraph(f"Predictive Intelligence &nbsp;·&nbsp; generated {generated} &nbsp;·&nbsp; served model: XGBoost with a 90% range", SMALL),
        Spacer(1, 7),
        boxed(Paragraph("<b>Simulated data.</b> NASA C-MAPSS is computer-simulated turbofan data, not measurements from a real aircraft. "
                        "These results show how the model performs on this benchmark only. They say nothing about real engines.", BODY),
              colors.HexColor("#fdf6ec"), colors.HexColor("#c9781a")),
        Paragraph("What was tested", HEADING),
        Paragraph("NASA supplies 100 test engines whose records stop some time before failure, and a separate answer file with the true "
                  "number of flights each had left. None of these engines was used to train, tune or calibrate the model. For each engine the "
                  "model saw its record up to the last flight, gave an estimate and a 90% range, and the estimate was compared with the answer file.", BODY),
        Paragraph("Results", HEADING),
    ]
    rows = [[Paragraph(f"<b>{h}</b>", CELL) for h in ("Measure", "Result", "What it means")],
            *[[Paragraph(a, CELL), Paragraph(f"<b>{b}</b>", CELL), Paragraph(c, CELL)] for a, b, c in [
                ("RMSE", f"{figures['RMSE']:.2f} flights", "Typical size of a miss; large misses count extra. Lower is better."),
                ("MAE", f"{figures['MAE']:.2f} flights", "Average size of a miss."),
                ("NASA score", f"{figures['NASA score']:.1f}", "PHM08 score (Saxena et al., 2008): late estimates cost more than early ones. Lower is better."),
                ("Range coverage", f"{figures['coverage']:.0f} of 100 engines", f"True figure (capped at {service.cap}) inside the 90% range. Average range width {figures['width']:.1f} flights."),
                ("Outside the range", f"{figures['below']} failed sooner, {figures['above']} lasted longer", "Failing sooner than the range is the costly direction."),
                ("Late estimates", f"{figures['late']} engines ({figures['late20']} by more than 20)", "The estimate was above the true figure."),
                ("Near failure", f"MAE {figures['near_mae']:.1f} flights ({figures['near_n']} engines)", "Engines with 30 or fewer flights truly left."),
                ("False end-of-life alarms", f"{figures['near_alarm']}", "Engines with more than 60 flights left that were estimated at 30 or fewer."),
            ]]]
    story += [styled(rows, [PAGE_WIDTH * w for w in (0.2, 0.27, 0.53)]),
              Paragraph(f"Errors are against the true figures as given. Against figures capped at {service.cap} flights (the furthest the model "
                        f"can see), RMSE is {figures['RMSE, truth capped']:.2f}.", SMALL),
              KeepTogether([Paragraph("Estimate against truth, every test engine", HEADING), scatter(table, service.cap)])]

    rows = [[Paragraph(f"<b>{h}</b>", CELL) for h in ("Engine", "Flights recorded", "True left", "Estimate", "90% range", "Error", "In range")]]
    for row in table.itertuples():
        rows.append([Paragraph(str(v), CELL) for v in (
            row.engine, row.flights, row.true_rul, f"{row.estimate:.1f}",
            f"{row.low:.1f}+" if row.high >= service.cap else f"{row.low:.1f} to {row.high:.1f}",
            f"{row.error:+.0f}", "yes" if row.inside else "<font color='#c0392b'><b>no</b></font>")])
    story += [Paragraph("Every engine", HEADING),
              Paragraph("Error = estimate minus true figure: positive means the estimate was late (too optimistic). Ranges are shown to one "
                        f"decimal because coverage is counted on the exact range; a range reaching {service.cap} is open-ended (\"+\"). "
                        f"\"In range\" compares the range with the true figure capped at {service.cap}.", SMALL), Spacer(1, 3),
              styled(rows, [PAGE_WIDTH * w for w in (0.1, 0.16, 0.13, 0.13, 0.2, 0.12, 0.16)]),
              Spacer(1, 10),
              Paragraph("Reproduce with <font face='Courier'>python scripts/test_report.py</font>. Data: A. Saxena, K. Goebel, D. Simon and N. Eklund, "
                        "\"Damage propagation modeling for aircraft engine run-to-failure simulation\", PHM08, 2008.", SMALL)]

    def footer(canvas, document):
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(MUTED)
        canvas.drawString(18 * mm, 10 * mm, "Predictive Intelligence · test results on simulated benchmark data")
        canvas.drawRightString(A4[0] - 18 * mm, 10 * mm, f"Page {document.page}")

    path.parent.mkdir(parents=True, exist_ok=True)
    document = SimpleDocTemplate(str(path), pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm, bottomMargin=18 * mm,
                                 title="Model test report: NASA C-MAPSS FD001", author="Predictive Intelligence")
    document.build(story, onFirstPage=footer, onLaterPages=footer)
    return figures


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", type=Path, default=None, help="where to write the PDF")
    args = parser.parse_args()
    service = EngineService()
    out = args.out or service.root / "reports" / "FD001_test_report.pdf"
    figures = build_pdf(test_results(service), service, out)
    print(f"Wrote {out}")
    for key, value in figures.items():
        print(f"  {key}: {value:.3f}" if isinstance(value, float) else f"  {key}: {value}")


if __name__ == "__main__":
    main()
