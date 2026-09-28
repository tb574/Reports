"""PDF version of the CPS daily revenue report.

Uses ReportLab with the built-in Helvetica fonts, which are not embedded, so
the file stays small enough to attach to the daily email.
"""

import datetime as dt

from reportlab.graphics.shapes import Drawing, Line, Rect, String
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (CondPageBreak, KeepTogether, Paragraph, SimpleDocTemplate,
                                Spacer, Table, TableStyle)

INK = colors.HexColor("#111827")
MUTED = colors.HexColor("#6b7280")
RULE = colors.HexColor("#e5e7eb")
FAINT = colors.HexColor("#f1f5f9")
TILE = colors.HexColor("#f8fafc")
BAR = colors.HexColor("#3b82f6")
BAR_LAST = colors.HexColor("#1e40af")
UP = colors.HexColor("#15803d")
DOWN = colors.HexColor("#b91c1c")

H1 = ParagraphStyle("h1", fontName="Helvetica-Bold", fontSize=17, leading=21, textColor=INK)
H2 = ParagraphStyle("h2", fontName="Helvetica-Bold", fontSize=12, leading=15, textColor=INK,
                    spaceBefore=14, spaceAfter=5)
H3 = ParagraphStyle("h3", fontName="Helvetica-Bold", fontSize=10, leading=13, textColor=INK,
                    spaceBefore=8, spaceAfter=3)
SMALL = ParagraphStyle("small", fontName="Helvetica", fontSize=8, leading=10, textColor=MUTED)
CELL = ParagraphStyle("cell", fontName="Helvetica", fontSize=8, leading=10, textColor=INK)


def _money(v, cur):
    return f"{cur} {v:,.2f}"


def _change(cur, prev):
    if not prev:
        return "n/a vs prior day"
    pct = (cur - prev) / prev * 100
    color = "#15803d" if pct >= 0 else "#b91c1c"
    arrow = "+" if pct >= 0 else "-"
    return f'<font color="{color}">{arrow}{abs(pct):.1f}%</font> vs prior day'


def _kpis(tiles, width):
    label = ParagraphStyle("kl", parent=SMALL)
    value = ParagraphStyle("kv", fontName="Helvetica-Bold", fontSize=13, leading=16, textColor=INK)
    sub = ParagraphStyle("ks", fontName="Helvetica", fontSize=7.5, leading=9.5, textColor=INK)
    cells = [[Paragraph(l, label), Paragraph(v, value), Paragraph(s, sub)] for l, v, s in tiles]
    rows = [cells[i:i + 4] for i in range(0, len(cells), 4)]
    t = Table(rows, colWidths=[width / 4] * 4)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), TILE),
        ("BOX", (0, 0), (-1, -1), 0.5, RULE),
        ("INNERGRID", (0, 0), (-1, -1), 3, colors.white),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    return t


def _grid(header, rows, widths, n_left=1):
    data = [header] + rows
    t = Table(data, colWidths=widths, repeatRows=1)
    style = [
        ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 8),
        ("FONT", (0, 1), (-1, -1), "Helvetica", 8),
        ("TEXTCOLOR", (0, 0), (-1, -1), INK),
        ("ALIGN", (n_left, 0), (-1, -1), "RIGHT"),
        ("LINEBELOW", (0, 0), (-1, 0), 1, RULE),
        ("LINEBELOW", (0, 1), (-1, -1), 0.4, FAINT),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]
    if not rows:
        data.append(["No activity"] + [""] * (len(header) - 1))
        t = Table(data, colWidths=widths)
        style.append(("TEXTCOLOR", (0, 1), (-1, -1), MUTED))
    t.setStyle(TableStyle(style))
    return t


def _stats_rows(rows, cur, publishers=None):
    out = []
    for r in sorted(rows, key=lambda r: r["income"], reverse=True):
        cr = r["conversions"] / r["clicks"] * 100 if r["clicks"] else 0
        row = [Paragraph(r["label"], CELL)]
        if publishers is not None:
            row.append(Paragraph(publishers.get(r["label"], "-"), CELL))
        row += [f'{r["clicks"]:,}', f'{r["conversions"]:,}', f"{cr:.2f}%",
                _money(r["income"], cur), _money(r["payout"], cur), _money(r["profit"], cur)]
        out.append(row)
    return out


def _stats_table(rows, first_col, width, cur, publishers=None):
    nums = ["Clicks", "Conv.", "CR", "Income", "Payout", "Profit"]
    num_w = [0.085, 0.065, 0.075, 0.13, 0.13, 0.12]
    if publishers is not None:
        header = [first_col, "Publisher"] + nums
        widths = [0.26, 0.135] + num_w
    else:
        header = [first_col] + nums
        widths = [0.395] + num_w
    return _grid(header, _stats_rows(rows, cur, publishers), [w * width for w in widths],
                 n_left=2 if publishers is not None else 1)


def _chart(day, series, width, cur):
    h, top, bottom = 150, 14, 14
    d = Drawing(width, h + top + bottom)
    peak = max((r["income"] for _, r in series), default=0)
    n = len(series)
    slot = width / max(n, 1)
    gap = min(2, slot * 0.15)
    d.add(Line(0, bottom, width, bottom, strokeColor=RULE, strokeWidth=0.6))
    best = max(series, key=lambda x: x[1]["income"])[0] if series else None
    for i, (date, r) in enumerate(series):
        x = i * slot + gap / 2
        bh = r["income"] / peak * h if peak else 0
        if bh > 0:
            d.add(Rect(x, bottom, slot - gap, max(bh, 1.5), fillColor=BAR_LAST if date == day else BAR,
                       strokeColor=None))
        else:
            d.add(Rect(x, bottom, slot - gap, 1, fillColor=RULE, strokeColor=None))
        if date in (day, best) and r["income"] > 0:
            d.add(String(x + (slot - gap) / 2, bottom + bh + 3, f'{r["income"]:,.0f}',
                         fontName="Helvetica-Bold", fontSize=7, fillColor=INK, textAnchor="middle"))
        if date.day == 1 or date.day % 5 == 0 or date == day:
            d.add(String(x + (slot - gap) / 2, 3, str(date.day), fontName="Helvetica", fontSize=7,
                         fillColor=MUTED, textAnchor="middle"))
    return d


def build_pdf(path, day, data, summarise, run_by, cur, demo=False):
    doc = SimpleDocTemplate(path, pagesize=A4, leftMargin=14 * mm, rightMargin=14 * mm,
                            topMargin=13 * mm, bottomMargin=13 * mm,
                            title=f"CPS Daily Revenue {day}", author="Affise daily report")
    width = doc.width
    t = summarise(data["day_by_affiliate"])
    p = summarise(data["prev_by_affiliate"])
    m = summarise(data["mtd_by_day"])
    days_in_month = ((day.replace(day=28) + dt.timedelta(days=4)).replace(day=1) - dt.timedelta(days=1)).day
    forecast = m["income"] / day.day * days_in_month if day.day else 0
    pairs = data.get("day_by_offer_affiliate", [])

    story = []
    if demo:
        story.append(Paragraph("Sample data - not real Affise figures.", SMALL))
    story += [Paragraph("CPS Daily Revenue Report", H1),
              Paragraph(f"{day.strftime('%A, %d %B %Y')} · Source: Affise", SMALL), Spacer(1, 8)]
    story.append(_kpis([
        ("Income (yesterday)", _money(t["income"], cur), _change(t["income"], p["income"])),
        ("Profit", _money(t["profit"], cur), f'{t["margin"]:.1f}% margin'),
        ("Conversions", f'{t["conversions"]:,}', f'{t["approved"]} approved · {t["pending"]} pending'),
        ("Clicks", f'{t["clicks"]:,}', f'CR {t["cr"]:.2f}% · EPC {_money(t["epc"], cur)}'),
        ("Month-to-date income", _money(m["income"], cur), f"{day.day} days"),
        ("Month-to-date profit", _money(m["profit"], cur), f'{m["margin"]:.1f}% margin'),
        ("Month forecast (income)", _money(forecast, cur), "run-rate"),
        ("MTD conversions", f'{m["conversions"]:,}', f'{m["declined"]} declined'),
    ], width))

    story.append(Paragraph("Revenue by publisher - yesterday", H2))
    story.append(_stats_table(data["day_by_affiliate"], "Publisher", width, cur))

    by_pub = {}
    for r in pairs:
        if r["clicks"] or r["conversions"]:
            by_pub.setdefault(r["publisher"], []).append(r)
    if by_pub:
        story.append(CondPageBreak(60 * mm))
        story.append(Paragraph("Offers run by each publisher - yesterday", H2))
        for pub, rows in sorted(by_pub.items(), key=lambda kv: summarise(kv[1])["income"], reverse=True):
            s = summarise(rows)
            n = len(rows)
            head = Paragraph(
                f'{pub} <font name="Helvetica" color="#6b7280" size="8">· {n} offer{"s" if n != 1 else ""} · '
                f'{s["clicks"]:,} clicks · {s["conversions"]:,} conv. · {_money(s["income"], cur)} income · '
                f'{_money(s["profit"], cur)} profit</font>', H3)
            story.append(KeepTogether([head, _stats_table(rows, "Offer", width, cur)])
                         if n <= 12 else head)
            if n > 12:
                story.append(_stats_table(rows, "Offer", width, cur))

    story.append(CondPageBreak(60 * mm))
    story.append(Paragraph("Revenue by offer - yesterday", H2))
    story.append(_stats_table(data["day_by_offer"], "Offer", width, cur, run_by(pairs)))

    by_date = {r["label"]: r for r in data["mtd_by_day"]}
    empty = {"income": 0.0, "profit": 0.0, "conversions": 0}
    series = [(d, by_date.get(d.isoformat(), empty))
              for d in (day.replace(day=i) for i in range(1, day.day + 1))]
    active = [r for _, r in series if r["income"] > 0]
    avg = sum(r["income"] for r in active) / len(active) if active else 0
    best_d, best_r = max(series, key=lambda x: x[1]["income"])
    weeks, weekly = [], {}
    for d, r in series:
        start = d - dt.timedelta(days=d.weekday())
        if start not in weekly:
            weekly[start] = {"days": [], "income": 0.0, "profit": 0.0, "conversions": 0}
            weeks.append(start)
        w = weekly[start]
        w["days"].append(d)
        w["income"] += r["income"]
        w["profit"] += r["profit"]
        w["conversions"] += r["conversions"]
    week_rows = [[f'{weekly[s]["days"][0].strftime("%d %b")} - {weekly[s]["days"][-1].strftime("%d %b")}',
                  f'{weekly[s]["conversions"]:,}', _money(weekly[s]["income"], cur),
                  _money(weekly[s]["profit"], cur)] for s in weeks]
    story.append(KeepTogether([
        Paragraph("Month-to-date daily income", H2),
        Paragraph(f'Best day {best_d.strftime("%d %b")} ({_money(best_r["income"], cur)}) · Average '
                  f'{_money(avg, cur)} across {len(active)} earning days · Darker bar = yesterday', SMALL),
        Spacer(1, 6),
        _chart(day, series, width, cur),
        Spacer(1, 8),
        _grid(["Week", "Conv.", "Income", "Profit"], week_rows,
              [width * w for w in (0.4, 0.2, 0.2, 0.2)]),
    ]))
    story += [Spacer(1, 12), Paragraph(
        'Income = amount networks pay us (Affise "charge"). Payout = publisher share (Affise "revenue"). '
        "Profit = Income - Payout. Includes pending conversions, which may still be declined by the network.",
        SMALL)]
    doc.build(story)
    return path
