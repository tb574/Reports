#!/usr/bin/env python3
"""Daily CPS revenue report from Affise.

Pulls yesterday's stats (plus the day before and the month-to-date) from the
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
    """GET /3.0/stats/custom sliced by one or more dimensions, all pages."""
    rows, page = [], 1
    while True:
        data = affise_get("/3.0/stats/custom", {
            "slice[]": slice_by if isinstance(slice_by, list) else [slice_by],
            "filter[date_from]": date_from.isoformat(),
            "filter[date_to]": date_to.isoformat(),
            "page": page,
            "limit": 500,
        })
        rows.extend(data.get("stats", []))
        pagination = data.get("pagination") or {}
        total = int(num(pagination.get("total_count")))
        per_page = int(num(pagination.get("per_page"))) or 1
        if not data.get("stats") or page * per_page >= total:
            return rows
        page += 1


def num(value):
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def slice_label(row, slice_by):
    label = row.get("slice", {}).get(slice_by)
    if isinstance(label, dict):
        name = label.get("title") or label.get("name") or label.get("login") or label.get("id")
        label = f"{name} (#{label.get('id')})" if label.get("id") not in (None, name) else str(name)
    return str(label) if label is not None else "—"


def normalise(row, slice_by):
    """Flatten one Affise stats row.

    Affise naming: `charge` is what the advertiser/network pays us (income),
    `revenue` is what we pay the publisher (payout). Profit = charge - revenue.
    """
    label = slice_label(row, slice_by)
    actions = row.get("actions", {})
    total = actions.get("total", {})
    confirmed = actions.get("confirmed", {})
    pending = actions.get("pending", {})
    declined = actions.get("declined", {})
    traffic = row.get("traffic", {})
    income = num(total.get("charge"))
    payout = num(total.get("revenue"))
    return {
        "label": label,
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
        "mtd_by_day": (month_start, day, "day"),
    }.items():
        data[key] = [normalise(r, slice_by) for r in fetch_stats(slice_by, a, b)]
    data["day_by_offer_affiliate"] = []
    for r in fetch_stats(["offer", "affiliate"], day, day):
        row = normalise(r, "offer")
        row["publisher"] = slice_label(r, "affiliate")
        data["day_by_offer_affiliate"].append(row)
    for r in data["mtd_by_day"]:
        # The day slice comes back as a bare day-of-month number.
        if r["label"].isdigit():
            r["label"] = month_start.replace(day=int(r["label"])).isoformat()
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
        "day_by_offer_affiliate": [dict(mk(*o), publisher=p[0]) for o, p in zip(offers, pubs)],
        "prev_by_affiliate": [mk(*p, scale=0.88) for p in pubs],
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


def run_by(pairs):
    """Offer label -> who ran it, e.g. "Bidder" or "Bidder $300 · IdeaClan $53"."""
    by_offer = {}
    for r in pairs:
        if r["clicks"] or r["conversions"]:
            by_offer.setdefault(r["label"], []).append(r)
    out = {}
    for offer, rows in by_offer.items():
        rows.sort(key=lambda r: (r["income"], r["clicks"]), reverse=True)
        names = [r["publisher"].split(" (#")[0] for r in rows]
        if len(rows) > 1:
            names = [f'{n} {r["income"]:,.0f}' for n, r in zip(names, rows)]
        out[offer] = " · ".join(names)
    return out


def table(title, rows, first_col, publishers=None, sub=False):
    rows = sorted(rows, key=lambda r: r["income"], reverse=True)
    cols = [first_col] + (["Publisher"] if publishers is not None else []) + \
        ["Clicks", "Conv.", "CR", "Income", "Payout", "Profit"]
    n_left = 2 if publishers is not None else 1
    head = "".join(f'<th style="text-align:{"left" if i < n_left else "right"};padding:8px;border-bottom:2px solid #e5e7eb">{h}</th>'
                   for i, h in enumerate(cols))
    body = ""
    for r in rows:
        cr = r["conversions"] / r["clicks"] * 100 if r["clicks"] else 0
        cells = [html.escape(r["label"])]
        if publishers is not None:
            cells.append(html.escape(publishers.get(r["label"], "—")))
        cells += [f'{r["clicks"]:,}', f'{r["conversions"]:,}', f"{cr:.2f}%",
                 money(r["income"]), money(r["payout"]), money(r["profit"])]
        body += "<tr>" + "".join(
            f'<td style="text-align:{"left" if i < n_left else "right"};padding:8px;border-bottom:1px solid #f1f5f9">{c}</td>'
            for i, c in enumerate(cells)) + "</tr>"
    if not rows:
        body = f'<tr><td colspan="{len(cols)}" style="padding:8px;color:#6b7280">No activity</td></tr>'
    h = (f'<h3 style="font-size:14px;margin:20px 0 6px">{title}</h3>' if sub
         else f'<h2 style="font-size:16px;margin:28px 0 8px">{title}</h2>')
    return (h +
            f'<table style="width:100%;border-collapse:collapse;font-size:13px">'
            f"<thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>")


def kpi(label, value, sub=""):
    return (f'<td style="padding:14px;background:#f8fafc;border:1px solid #e5e7eb;border-radius:8px;width:25%">'
            f'<div style="font-size:12px;color:#6b7280">{label}</div>'
            f'<div style="font-size:20px;font-weight:600;margin-top:4px">{value}</div>'
            f'<div style="font-size:12px;margin-top:2px">{sub}</div></td>')


def publisher_sections(pairs):
    """One block per publisher listing every offer it ran yesterday."""
    by_pub = {}
    for r in pairs:
        if r["clicks"] or r["conversions"]:
            by_pub.setdefault(r["publisher"], []).append(r)
    if not by_pub:
        return ""
    out = '<h2 style="font-size:16px;margin:28px 0 0">Offers run by each publisher — yesterday</h2>'
    for pub, rows in sorted(by_pub.items(), key=lambda kv: summarise(kv[1])["income"], reverse=True):
        t = summarise(rows)
        title = (f'{html.escape(pub)} <span style="font-weight:400;color:#6b7280">· {len(rows)} offer{"s" if len(rows) != 1 else ""} · '
                 f'{t["clicks"]:,} clicks · {t["conversions"]:,} conv. · {money(t["income"])} income · '
                 f'{money(t["profit"])} profit</span>')
        out += table(title, rows, "Offer", sub=True)
    return out


def trend_chart(day, rows):
    """Month-to-date income as an email-safe column chart plus weekly totals.

    Built from tables and fixed-height divs (no SVG/JS) so it renders in Gmail
    and Outlook. Hovering a column shows its figures via the title attribute.
    """
    by_date = {r["label"]: r for r in rows}
    empty = {"income": 0.0, "profit": 0.0, "conversions": 0, "clicks": 0}
    days = [day.replace(day=i) for i in range(1, day.day + 1)]
    series = [(d, by_date.get(d.isoformat(), empty)) for d in days]
    peak = max((r["income"] for _, r in series), default=0)
    best = max(series, key=lambda x: x[1]["income"])
    active = [r for _, r in series if r["income"] > 0]
    avg = sum(r["income"] for r in active) / len(active) if active else 0
    height = 150

    cols, labels = "", ""
    for d, r in series:
        h = round(r["income"] / peak * height) if peak else 0
        tip = html.escape(f'{d.strftime("%a %d %b")}: {money(r["income"])} income, '
                          f'{money(r["profit"])} profit, {r["conversions"]} conv.', quote=True)
        # Only yesterday and the best day carry a value label.
        note = ""
        if d in (day, best[0]) and r["income"] > 0:
            note = (f'<div style="font-size:10px;font-weight:600;color:#111827;white-space:nowrap;'
                    f'text-align:center;margin-bottom:2px">{r["income"]:,.0f}</div>')
        if h > 0:
            color = "#1e40af" if d == day else "#3b82f6"
            bar = f'<div style="height:{max(h, 3)}px;background:{color};border-radius:4px 4px 0 0"></div>'
        else:
            bar = '<div style="height:2px;background:#e5e7eb"></div>'
        cols += (f'<td title="{tip}" valign="bottom" style="padding:0 1px;vertical-align:bottom;'
                 f'height:{height + 16}px">{note}{bar}</td>')
        show = d.day == 1 or d.day % 5 == 0 or d == day
        labels += (f'<td style="padding:4px 0 0;font-size:10px;color:#6b7280;text-align:center">'
                   f'{d.day if show else ""}</td>')

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
    cell = 'padding:6px 8px;border-bottom:1px solid #f1f5f9;text-align:right'
    week_rows = ""
    for start in weeks:
        w = weekly[start]
        span = f'{w["days"][0].strftime("%d %b")} – {w["days"][-1].strftime("%d %b")}'
        week_rows += (f'<tr><td style="{cell};text-align:left">{span}</td>'
                      f'<td style="{cell}">{w["conversions"]:,}</td>'
                      f'<td style="{cell}">{money(w["income"])}</td>'
                      f'<td style="{cell}">{money(w["profit"])}</td></tr>')
    th = 'padding:6px 8px;border-bottom:2px solid #e5e7eb;text-align:right;font-weight:600'

    return f"""<h2 style="font-size:16px;margin:28px 0 2px">Month-to-date daily income</h2>
<p style="font-size:12px;color:#6b7280;margin:0 0 12px">Best day {best[0].strftime("%d %b")} ({money(best[1]["income"])})
· Average {money(avg)} across {len(active)} earning days · Darker bar = yesterday</p>
<table style="width:100%;border-collapse:collapse;table-layout:fixed">
<tr>{cols}</tr><tr style="border-top:1px solid #d1d5db">{labels}</tr></table>
<table style="width:100%;border-collapse:collapse;font-size:13px;margin-top:16px">
<thead><tr><th style="{th};text-align:left">Week</th><th style="{th}">Conv.</th>
<th style="{th}">Income</th><th style="{th}">Profit</th></tr></thead>
<tbody>{week_rows}</tbody></table>"""



def render_html(day, data, demo=False):
    t = summarise(data["day_by_affiliate"])
    p = summarise(data["prev_by_affiliate"])
    m = summarise(data["mtd_by_day"])
    days_in_month = ((day.replace(day=28) + dt.timedelta(days=4)).replace(day=1) - dt.timedelta(days=1)).day
    forecast = m["income"] / day.day * days_in_month if day.day else 0

    trend = trend_chart(day, data["mtd_by_day"])

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
{table("Revenue by publisher — yesterday", data["day_by_affiliate"], "Publisher")}
{publisher_sections(data.get("day_by_offer_affiliate", []))}
{table("Revenue by offer — yesterday", data["day_by_offer"], "Offer", run_by(data.get("day_by_offer_affiliate", [])))}
{trend}
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
