"""A downloadable engine report, as a PDF.

Built from the engine's fact sheet, the same one the screens use, so the
report cannot say anything the application did not. Light background, so it
prints cleanly.
"""

from datetime import datetime, timezone
from io import BytesIO

import pandas as pd
from reportlab.graphics.shapes import Drawing, Line, PolyLine, Polygon, String
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import KeepTogether, ListFlowable, ListItem, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from src.assistant.knowledge import SAFETY_NOTE

INK = colors.HexColor("#1c2530")
MUTED = colors.HexColor("#5d6875")
LINE = colors.HexColor("#d9dee4")
ORANGE = colors.HexColor("#d97757")
BURGUNDY = colors.HexColor("#7b2d3b")
STATUS_COLOUR = {
    "no_measurable_wear": colors.HexColor("#2f8f5b"), "early_wear": colors.HexColor("#9a7b4f"),
    "advanced_wear": colors.HexColor("#c9781a"), "near_end_of_predicted_life": colors.HexColor("#c0392b"),
}

BODY = ParagraphStyle("body", fontName="Helvetica", fontSize=10, leading=14.5, textColor=INK, alignment=TA_LEFT)
SMALL = ParagraphStyle("small", parent=BODY, fontSize=8.5, leading=12, textColor=MUTED)
TITLE = ParagraphStyle("title", parent=BODY, fontName="Helvetica-Bold", fontSize=18, leading=22)
HEADING = ParagraphStyle("heading", parent=BODY, fontName="Helvetica-Bold", fontSize=11.5, leading=15, spaceBefore=12, spaceAfter=5, textColor=BURGUNDY)
CELL = ParagraphStyle("cell", parent=BODY, fontSize=9, leading=12)
PAGE_WIDTH = A4[0] - 36 * mm


def range_text(facts: dict) -> str:
    if facts["range_is_open_ended"] or facts["range_high_cycles"] is None:
        return f"at least {facts['range_low_cycles']} flights"
    return f"{facts['range_low_cycles']} to {facts['range_high_cycles']} flights"


def boxed(content, background, border, padding: int = 8) -> Table:
    table = Table([[content]], colWidths=[PAGE_WIDTH])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), background), ("BOX", (0, 0), (-1, -1), 0.8, border),
        ("LEFTPADDING", (0, 0), (-1, -1), padding), ("RIGHTPADDING", (0, 0), (-1, -1), padding),
        ("TOPPADDING", (0, 0), (-1, -1), padding - 2), ("BOTTOMPADDING", (0, 0), (-1, -1), padding - 1),
    ]))
    return table


def chart(estimates: pd.DataFrame, cap: int):
    """Estimate and range over the recorded flights."""
    if estimates.empty:
        return Paragraph("Fewer than 31 flights are on record, so there is no estimate history to draw.", SMALL)
    width, height, left, right, top, bottom = PAGE_WIDTH, 150, 32, 8, 8, 26
    first, last = float(estimates["cycle"].min()), float(estimates["cycle"].max())
    span, top_value = max(last - first, 1.0), cap + 15

    def x(cycle: float) -> float:
        return left + (cycle - first) / span * (width - left - right)

    def y(value: float) -> float:
        return bottom + min(max(value, 0), top_value) / top_value * (height - top - bottom)

    drawing = Drawing(width, height)
    for value in range(0, top_value, 25):
        drawing.add(Line(left, y(value), width - right, y(value), strokeColor=colors.HexColor("#e3e7ec"), strokeWidth=0.6))
        drawing.add(String(left - 5, y(value) - 3, str(value), fontSize=7.5, fillColor=MUTED, textAnchor="end"))
    for cycle in sorted({int(first), int(first + span / 2), int(last)}):
        drawing.add(String(x(cycle), bottom - 11, str(cycle), fontSize=7.5, fillColor=MUTED, textAnchor="middle"))
    drawing.add(String((left + width - right) / 2, 2, "Flights completed", fontSize=7.5, fillColor=MUTED, textAnchor="middle"))
    drawing.add(Line(left, y(cap), width - right, y(cap), strokeColor=colors.HexColor("#9aa5b1"), strokeWidth=0.7, strokeDashArray=[4, 3]))

    band = []
    for cycle, value in zip(estimates["cycle"], estimates["high"]):
        band += [x(cycle), y(value)]
    for cycle, value in zip(estimates["cycle"][::-1], estimates["low"][::-1]):
        band += [x(cycle), y(value)]
    drawing.add(Polygon(band, fillColor=colors.Color(0.85, 0.47, 0.34, alpha=0.2), strokeColor=None))
    line = []
    for cycle, value in zip(estimates["cycle"], estimates["estimate"]):
        line += [x(cycle), y(value)]
    drawing.add(PolyLine(line, strokeColor=ORANGE, strokeWidth=1.6))
    return drawing


def render_report(facts: dict, estimates: pd.DataFrame, source_note: str) -> bytes:
    """Build the PDF and return its bytes."""
    status_colour = STATUS_COLOUR[facts["status"]["key"]]
    generated = datetime.now(timezone.utc).strftime("%d %B %Y, %H:%M UTC")
    story = [
        Paragraph(f"Engine report: {facts['engine']}", TITLE),
        Paragraph(f"Predictive Intelligence &nbsp;·&nbsp; generated {generated} &nbsp;·&nbsp; {source_note}", SMALL),
        Spacer(1, 7),
        boxed(Paragraph(f"<b>Please note.</b> {SAFETY_NOTE} The model was trained on NASA C-MAPSS simulated data "
                        "and has not been validated on real engines.", BODY), colors.HexColor("#fdf6ec"), colors.HexColor("#c9781a")),
        Paragraph("Summary", HEADING),
    ]

    status = Table([[Paragraph(f"<font color='{status_colour.hexval()}' size='13'><b>{facts['status']['label']}</b></font><br/>"
                               f"{facts['status']['plain']}", BODY)]], colWidths=[PAGE_WIDTH])
    status.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f4f6f8")), ("LINEBEFORE", (0, 0), (0, -1), 4, status_colour),
                                ("LEFTPADDING", (0, 0), (-1, -1), 10), ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 8)]))
    story += [status, Spacer(1, 7)]

    def figure(label: str, value: str) -> Paragraph:
        return Paragraph(f"<font size='8' color='{MUTED.hexval()}'>{label}</font><br/><font size='15'><b>{value}</b></font>",
                         ParagraphStyle("figure", parent=BODY, leading=20))

    figures = Table([[figure("Estimated flights remaining", str(facts["estimate_cycles"])),
                      figure(f"Likely range ({facts['range_confidence_percent']}%)", range_text(facts)),
                      figure("Flights on record", str(facts["cycles_recorded"]))]], colWidths=[PAGE_WIDTH / 3] * 3)
    figures.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.7, LINE), ("LEFTPADDING", (0, 0), (-1, -1), 9),
                                 ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 9)]))
    story += [figures, Spacer(1, 6)]

    if facts["range_is_open_ended"]:
        story.append(Paragraph(f"The model sees no measurable wear yet. It can only see about {facts['rul_cap_cycles']} flights ahead, "
                               "so it reports a minimum.", BODY))
    else:
        story.append(Paragraph("For about nine engines in ten the true figure falls inside a range like this; for about one in ten it "
                               "does not. Some engines have failed sooner than the lower figure, so it is not a safety limit.", BODY))
    if facts["limited_history"]:
        story.append(Paragraph(f"<font color='#9a5a0c'>Only {facts['cycles_recorded']} flights are on record, fewer than the 31 the model "
                               "was tested with. Treat this estimate with extra caution.</font>", BODY))

    warnings = facts.get("data_warnings", [])
    if warnings:
        items = [Paragraph("<b>Check the data before relying on this report</b>", BODY)] + [Paragraph(f"• {w}", BODY) for w in warnings]
        story += [Spacer(1, 6), boxed(items, colors.HexColor("#fdf6ec"), colors.HexColor("#c9781a"))]

    story += [KeepTogether([
        Paragraph("How the estimate has changed", HEADING), chart(estimates, facts["rul_cap_cycles"]),
        Paragraph(f"Orange line: estimated flights remaining. Shaded band: the range. Dashed line: the furthest the model can see "
                  f"({facts['rul_cap_cycles']} flights).", SMALL)])]

    rows = [[Paragraph(f"<b>{h}</b>", CELL) for h in ["Measurement", "Early in life", "Recently", "Now", "Effect on the estimate"]]]
    for reason in facts["main_reasons"]:
        lowered = reason["cycles"] < 0
        rows.append([
            Paragraph(f"{reason['description']} ({reason['symbol']})", CELL),
            Paragraph(f"{reason['early_life_level']} {reason['unit']}", CELL), Paragraph(f"{reason['recent_level']} {reason['unit']}", CELL),
            Paragraph(f"{reason['movement']} early life", CELL),
            Paragraph(f"<font color='{'#b8650e' if lowered else '#177a6f'}'>{'lowered' if lowered else 'raised'} it by "
                      f"{abs(reason['cycles']):g} flights</font>", CELL)])
    reasons = Table(rows, colWidths=[PAGE_WIDTH * w for w in (0.31, 0.16, 0.16, 0.16, 0.21)], repeatRows=1)
    reasons.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, -1), 0.5, LINE), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                                 ("LEFTPADDING", (0, 0), (-1, -1), 4), ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
    story += [KeepTogether([
        Paragraph("What moved the estimate", HEADING), reasons, Spacer(1, 4),
        Paragraph(f"Effects are relative to the model's average estimate of {facts['model_average_estimate_cycles']} flights. These are the "
                  "readings the model relied on. They do not identify a faulty part or prove a mechanical cause.", SMALL)])]

    story += [KeepTogether([Paragraph("Something to consider", HEADING), Paragraph(facts["status"]["consider"], BODY),
                            Paragraph(f"Status and suggestion: {facts['status']['basis']}.", SMALL)])]

    error = facts["model"]["typical_error_cycles"]
    trust = Table([
        [Paragraph("<b>Model</b>", CELL), Paragraph(facts["model"]["name"], CELL)],
        [Paragraph("<b>Typical error on unseen test engines</b>", CELL), Paragraph("not available" if error is None else f"about {error} flights", CELL)],
        [Paragraph("<b>Range checked on test engines</b>", CELL),
         Paragraph(f"{facts['model']['measured_range_coverage_percent']:g}% of 100 engines fell inside their range "
                   f"(target {facts['range_confidence_percent']}%)", CELL)],
        [Paragraph("<b>Furthest the model can see</b>", CELL), Paragraph(f"{facts['rul_cap_cycles']} flights", CELL)],
    ], colWidths=[PAGE_WIDTH * 0.38, PAGE_WIDTH * 0.62])
    trust.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, -1), 0.5, LINE), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                               ("LEFTPADDING", (0, 0), (-1, -1), 4), ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
    story += [KeepTogether([Paragraph("How far to trust this", HEADING), trust, Spacer(1, 6),
                            ListFlowable([ListItem(Paragraph(item, BODY), leftIndent=12) for item in facts["limitations"]],
                                         bulletType="bullet", bulletFontSize=7, leftIndent=12)])]

    story += [Spacer(1, 12), Paragraph(
        "This report was produced automatically from the model's results for this engine. It supports a decision about where to look "
        "first. It does not replace inspection, approved maintenance procedures, or the judgement of qualified engineers.", SMALL)]

    def footer(canvas, document):
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(MUTED)
        canvas.drawString(18 * mm, 10 * mm, "Predictive Intelligence · research demonstration on simulated data")
        canvas.drawRightString(A4[0] - 18 * mm, 10 * mm, f"Page {document.page}")

    buffer = BytesIO()
    document = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm, bottomMargin=18 * mm,
                                 title=f"Engine report: {facts['engine']}", author="Predictive Intelligence")
    document.build(story, onFirstPage=footer, onLaterPages=footer)
    return buffer.getvalue()
