#!/usr/bin/env python3
"""Daily CPS revenue report from Affise.

Pulls yesterday's stats (plus the two days before it and the month-to-date) from the
Affise Admin API and writes:
  * an HTML report ready to email to management
  * a CSV row per day for the Google Drive log sheet

Usage:
  AFFISE_API_KEY=xxxx python3 daily_report.py              # report for yesterday
  AFFISE_API_KEY=xxxx python3 daily_report.py 2026-09-27   # report for a given day
  python3 daily_report.py --demo                           # sample data, no API

Stdlib only, so it runs anywhere Python 3.9+ is available.
"""

import csv
import datetime as dt
import html
import json
import os
import sys
import urllib.parse
import urllib.request

API_URL = os.environ.get("AFFISE_API_URL", "https://api-nyjltb.affise.com")
API_KEY = os.environ.get("AFFISE_API_KEY", "")
CURRENCY = os.environ.get("REPORT_CURRENCY", "USD")
OUT_DIR = os.environ.get("REPORT_OUT_DIR", os.path.join(os.path.dirname(__file__), "output"))


# --------------------------------------------------------------------------- API

def affise_get(path, params):
    query = urllib.parse.urlencode(params, doseq=True)
    req = urllib.request.Request(f"{API_URL}{path}?{query}", headers={"API-Key": API_KEY})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode())


def fetch_stats(slice_by, date_from, date_to):
    """GET /3.0/stats/custom sliced by one dimension, all pages."""
    rows, page = [], 1
    while True:
        data = affise_get("/3.0/stats/custom", {
            "slice[]": [slice_by],
            "filter[date_from]": date_from.isoformat(),
            "filter[date_to]": date_to.isoformat(),
            "filter[currency]": CURRENCY,
            "page": page,
            "limit": 500,
        })
        rows.extend(data.get("stats", []))
        pagination = data.get("pagination") or {}
        if not pagination.get("next_page"):
            return rows
        page += 1


def num(value):
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def normalise(row, slice_by):
    """Flatten one Affise stats row.

    Affise naming: `charge` is what the advertiser/network pays us (income),
    `revenue` is what we pay the publisher (payout). Profit = charge - revenue.
    """
    label = row.get("slice", {}).get(slice_by)
    if isinstance(label, dict):
        name = label.get("title") or label.get("name") or label.get("login") or label.get("id")
        label = f"{name} (#{label.get('id')})" if label.get("id") not in (None, name) else str(name)
    actions = row.get("actions", {})
    total = actions.get("total", {})
    confirmed = actions.get("confirmed", {})
    pending = actions.get("pending", {})
    declined = actions.get("declined", {})
    traffic = row.get("traffic", {})
    income = num(total.get("charge"))
    payout = num(total.get("revenue"))
    return {
        "label": str(label) if label is not None else "—",
        "clicks": int(num(traffic.get("raw"))),
        "unique_clicks": int(num(traffic.get("uniq"))),
        "conversions": int(num(total.get("count"))),
        "approved": int(num(confirmed.get("count"))),
        "pending": int(num(pending.get("count"))),
        "declined": int(num(declined.get("count"))),
        "income": income,
        "payout": payout,
        "profit": income - payout,
        "approved_income": num(confirmed.get("charge")),
        "pending_income": num(pending.get("charge")),
    }


def summarise(rows):
    keys = ["clicks", "unique_clicks", "conversions", "approved", "pending", "declined",
            "income", "payout", "profit", "approved_income", "pending_income"]
    out = {k: sum(r[k] for r in rows) for k in keys}
    out["cr"] = out["conversions"] / out["clicks"] * 100 if out["clicks"] else 0.0
    out["epc"] = out["income"] / out["clicks"] if out["clicks"] else 0.0
    out["margin"] = out["profit"] / out["income"] * 100 if out["income"] else 0.0
    return out


def collect(day):
    prev = day - dt.timedelta(days=1)
    month_start = day.replace(day=1)
    data = {}
    for key, (a, b, slice_by) in {
        "day_by_affiliate": (day, day, "affiliate"),
        "day_by_offer": (day, day, "offer"),
        "prev_by_affiliate": (prev, prev, "affiliate"),
        "last3_by_day": (day - dt.timedelta(days=2), day, "day"),
        "mtd_by_day": (month_start, day, "day"),
    }.items():
        data[key] = [normalise(r, slice_by) for r in fetch_stats(slice_by, a, b)]
    return data


# -------------------------------------------------------------------------- demo

def demo_data(day):
    pubs = [("IdeaClan (#4)", 5210, 61, 1480.0, 1036.0), ("adsiduous (#5)", 2890, 22, 610.0, 427.0),
            ("Bold Story (#1)", 1340, 18, 540.0, 378.0)]
    offers = [("Nike-US-IMNY", 3100, 40, 1120.0, 784.0), ("Swimply-US-DD", 2400, 25, 690.0, 483.0),
              ("Carwow-UK-IMNY", 3940, 36, 820.0, 574.0)]

    def mk(label, clicks, conv, inc, pay, scale=1.0):
        c = int(conv * scale)
        return {"label": label, "clicks": int(clicks * scale), "unique_clicks": int(clicks * scale * .86),
                "conversions": c, "approved": int(c * .6), "pending": c - int(c * .6) - int(c * .05),
                "declined": int(c * .05), "income": inc * scale, "payout": pay * scale,
                "profit": (inc - pay) * scale, "approved_income": inc * scale * .6,
                "pending_income": inc * scale * .35}

    mtd = []
    for i in range(day.day):
        d = day.replace(day=i + 1)
        s = 0.7 + ((i * 37) % 11) / 20
        mtd.append(mk(d.isoformat(), 9440, 101, 2630.0, 1841.0, s))
    return {
        "day_by_affiliate": [mk(*p) for p in pubs],
        "day_by_offer": [mk(*o) for o in offers],
        "prev_by_affiliate": [mk(*p, scale=0.88) for p in pubs],
        "last3_by_day": [mk((day - dt.timedelta(days=i)).isoformat(), 9440, 101, 2630.0, 1841.0, s)
                         for i, s in ((2, 0.81), (1, 0.88), (0, 1.0))],
        "mtd_by_day": mtd,
    }


# ------------------------------------------------------------------------ output

def money(v):
    return f"{CURRENCY} {v:,.2f}"


def delta(cur, prev):
    if not prev:
        return '<span style="color:#6b7280">n/a</span>'
    pct = (cur - prev) / prev * 100
    color = "#15803d" if pct >= 0 else "#b91c1c"
    arrow = "▲" if pct >= 0 else "▼"
    return f'<span style="color:{color}">{arrow} {abs(pct):.1f}%</span>'


def table(title, rows, first_col, by_label=False, total=False):
    rows = sorted(rows, key=lambda r: r["label"]) if by_label else sorted(rows, key=lambda r: r["income"], reverse=True)
    head = "".join(f'<th style="text-align:{"left" if i == 0 else "right"};padding:8px;border-bottom:2px solid #e5e7eb">{h}</th>'
                   for i, h in enumerate([first_col, "Clicks", "Conv.", "CR", "Income", "Payout", "Profit"]))
    body = ""
    for r in rows:
        cr = r["conversions"] / r["clicks"] * 100 if r["clicks"] else 0
        cells = [html.escape(r["label"]), f'{r["clicks"]:,}', f'{r["conversions"]:,}', f"{cr:.2f}%",
                 money(r["income"]), money(r["payout"]), money(r["profit"])]
        body += "<tr>" + "".join(
            f'<td style="text-align:{"left" if i == 0 else "right"};padding:8px;border-bottom:1px solid #f1f5f9">{c}</td>'
            for i, c in enumerate(cells)) + "</tr>"
    if not rows:
        body = '<tr><td colspan="7" style="padding:8px;color:#6b7280">No activity</td></tr>'
    elif total:
        s = summarise(rows)
        cells = ["Total", f'{s["clicks"]:,}', f'{s["conversions"]:,}', f'{s["cr"]:.2f}%',
                 money(s["income"]), money(s["payout"]), money(s["profit"])]
        body += "<tr>" + "".join(
            f'<td style="text-align:{"left" if i == 0 else "right"};padding:8px;font-weight:600;border-top:2px solid #e5e7eb">{c}</td>'
            for i, c in enumerate(cells)) + "</tr>"
    return (f'<h2 style="font-size:16px;margin:28px 0 8px">{title}</h2>'
            f'<table style="width:100%;border-collapse:collapse;font-size:13px">'
            f"<thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>")


def kpi(label, value, sub=""):
    return (f'<td style="padding:14px;background:#f8fafc;border:1px solid #e5e7eb;border-radius:8px;width:25%">'
            f'<div style="font-size:12px;color:#6b7280">{label}</div>'
            f'<div style="font-size:20px;font-weight:600;margin-top:4px">{value}</div>'
            f'<div style="font-size:12px;margin-top:2px">{sub}</div></td>')


def render_html(day, data, demo=False):
    t = summarise(data["day_by_affiliate"])
    p = summarise(data["prev_by_affiliate"])
    m = summarise(data["mtd_by_day"])
    days_in_month = ((day.replace(day=28) + dt.timedelta(days=4)).replace(day=1) - dt.timedelta(days=1)).day
    forecast = m["income"] / day.day * days_in_month if day.day else 0

    trend = ""
    peak = max((r["income"] for r in data["mtd_by_day"]), default=0) or 1
    for r in sorted(data["mtd_by_day"], key=lambda r: r["label"]):
        w = r["income"] / peak * 100
        trend += (f'<tr><td style="padding:3px 8px;font-size:12px;color:#6b7280;white-space:nowrap">{html.escape(r["label"])}</td>'
                  f'<td style="width:100%"><div style="background:#2563eb;height:12px;width:{w:.1f}%;border-radius:3px"></div></td>'
                  f'<td style="padding:3px 8px;font-size:12px;text-align:right;white-space:nowrap">{money(r["income"])}</td></tr>')

    banner = ('<p style="background:#fef3c7;padding:8px 12px;border-radius:6px;font-size:13px">'
              "Sample data — not real Affise figures.</p>") if demo else ""

    return f"""<!doctype html><html><head><meta charset="utf-8"><title>CPS Daily Revenue {day}</title></head>
<body style="font-family:-apple-system,Segoe UI,Roboto,Arial,sans-serif;color:#111827;max-width:820px;margin:0 auto;padding:24px">
{banner}
<h1 style="font-size:22px;margin:0">CPS Daily Revenue Report</h1>
<p style="color:#6b7280;margin:4px 0 20px">{day.strftime('%A, %d %B %Y')} · Source: Affise</p>
<table style="width:100%;border-spacing:8px;margin:0 -8px"><tr>
{kpi("Income (yesterday)", money(t["income"]), delta(t["income"], p["income"]) + " vs prior day")}
{kpi("Profit", money(t["profit"]), f'{t["margin"]:.1f}% margin')}
{kpi("Conversions", f'{t["conversions"]:,}', f'{t["approved"]} approved · {t["pending"]} pending')}
{kpi("Clicks", f'{t["clicks"]:,}', f'CR {t["cr"]:.2f}% · EPC {money(t["epc"])}')}
</tr><tr>
{kpi("Month-to-date income", money(m["income"]), f'{day.day} days')}
{kpi("Month-to-date profit", money(m["profit"]), f'{m["margin"]:.1f}% margin')}
{kpi("Month forecast (income)", money(forecast), "run-rate")}
{kpi("MTD conversions", f'{m["conversions"]:,}', f'{m["declined"]} declined')}
</tr></table>
{table("Last 3 days (yesterday and the 2 days before)", data["last3_by_day"], "Date", by_label=True, total=True)}
{table("Revenue by publisher — yesterday", data["day_by_affiliate"], "Publisher")}
{table("Revenue by offer — yesterday", data["day_by_offer"], "Offer")}
<h2 style="font-size:16px;margin:28px 0 8px">Month-to-date daily income</h2>
<table style="width:100%;border-collapse:collapse">{trend}</table>
<p style="font-size:11px;color:#9ca3af;margin-top:28px">Income = amount networks pay us (Affise "charge"). Payout = publisher share
(Affise "revenue"). Profit = Income − Payout. Includes pending conversions, which may still be declined by the network.</p>
</body></html>"""


def append_log(day, data):
    t = summarise(data["day_by_affiliate"])
    path = os.path.join(OUT_DIR, "daily_log.csv")
    new = not os.path.exists(path)
    with open(path, "a", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["Date", "Clicks", "Conversions", "Approved", "Pending", "Declined",
                        "Income", "Payout", "Profit", "Margin %", "CR %", "EPC", "Top publisher", "Top offer"])
        top_pub = max(data["day_by_affiliate"], key=lambda r: r["income"], default={"label": ""})["label"]
        top_off = max(data["day_by_offer"], key=lambda r: r["income"], default={"label": ""})["label"]
        w.writerow([day.isoformat(), t["clicks"], t["conversions"], t["approved"], t["pending"], t["declined"],
                    f'{t["income"]:.2f}', f'{t["payout"]:.2f}', f'{t["profit"]:.2f}', f'{t["margin"]:.1f}',
                    f'{t["cr"]:.2f}', f'{t["epc"]:.4f}', top_pub, top_off])
    return path


def main(argv):
    demo = "--demo" in argv
    args = [a for a in argv if not a.startswith("--")]
    day = dt.date.fromisoformat(args[0]) if args else dt.date.today() - dt.timedelta(days=1)
    if not demo and not API_KEY:
        sys.exit("Set AFFISE_API_KEY (Affise → Settings → Security → API key), or run with --demo.")
    data = demo_data(day) if demo else collect(day)
    os.makedirs(OUT_DIR, exist_ok=True)
    report = os.path.join(OUT_DIR, f"cps_revenue_{day.isoformat()}{'_demo' if demo else ''}.html")
    with open(report, "w") as f:
        f.write(render_html(day, data, demo))
    print(report)
    if not demo:
        print(append_log(day, data))
    with open(os.path.join(OUT_DIR, f"raw_{day.isoformat()}{'_demo' if demo else ''}.json"), "w") as f:
        json.dump(data, f, indent=2)


if __name__ == "__main__":
    main(sys.argv[1:])
