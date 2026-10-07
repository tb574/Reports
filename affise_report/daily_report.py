#!/usr/bin/env python3
"""Daily CPS revenue report from Affise.

Pulls yesterday's and the day before's stats, the whole of last month and month-to-date from the
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
    """GET /3.0/stats/custom sliced by one dimension (or a list of them), all pages."""
    # A bare "day" slice only returns the day of the month, so add year and month to get a full date.
    slices = ["year", "month", "day"] if slice_by == "day" else (
        list(slice_by) if isinstance(slice_by, (list, tuple)) else [slice_by])
    # No currency filter: unfiltered, Affise converts every conversion into the account currency (USD).
    # Filtering by currency drops clicks and every conversion in other currencies (e.g. EUR offers).
    rows, page = [], 1
    while True:
        data = affise_get("/3.0/stats/custom", {
            "slice[]": slices,
            "filter[date_from]": date_from.isoformat(),
            "filter[date_to]": date_to.isoformat(),
            "page": page,
            "limit": 500,
        })
        if data.get("status") != 1:
            raise RuntimeError(f"Affise error: {data.get('error') or data}")
        stats = data.get("stats", [])
        rows.extend(stats)
        pagination = data.get("pagination") or {}
        per_page = int(pagination.get("per_page") or len(stats) or 1)
        if not stats or page * per_page >= int(pagination.get("total_count") or 0):
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
    sl = row.get("slice", {})
    label = sl.get(slice_by)
    if slice_by == "day" and "year" in sl and "month" in sl:
        label = dt.date(int(sl["year"]), int(sl["month"]), int(sl["day"])).isoformat()
    elif isinstance(label, dict):
        name = label.get("title") or label.get("name") or label.get("login") or label.get("id")
        label = f"{name} (#{label.get('id')})" if label.get("id") not in (None, name) else str(name)
    # Affise sends an empty list instead of an object when a row has no data.
    obj = lambda v: v if isinstance(v, dict) else {}
    actions = obj(row.get("actions"))
    total = obj(actions.get("total"))
    confirmed = obj(actions.get("confirmed"))
    pending = obj(actions.get("pending"))
    declined = obj(actions.get("declined"))
    traffic = obj(row.get("traffic"))
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
    lm_end = month_start - dt.timedelta(days=1)
    lm_start = lm_end.replace(day=1)
    data = {}
    for key, (a, b, slice_by) in {
        "day_by_affiliate": (day, day, "affiliate"),
        "day_by_offer": (day, day, "offer"),
        "prev_by_affiliate": (prev, prev, "affiliate"),
        "prev_by_offer": (prev, prev, "offer"),
        "lastmonth_by_affiliate": (lm_start, lm_end, "affiliate"),
        "lastmonth_by_offer": (lm_start, lm_end, "offer"),
        "mtd_by_day": (month_start, day, "day"),
    }.items():
        data[key] = [normalise(r, slice_by) for r in fetch_stats(slice_by, a, b)]
    for key, (a, b) in {"day_campaigns": (day, day), "prev_campaigns": (prev, prev),
                        "lastmonth_campaigns": (lm_start, lm_end)}.items():
        data[key] = count_campaigns(fetch_stats(["affiliate", "offer"], a, b))
    return data


def count_campaigns(rows):
    """Campaigns per publisher: the offers that publisher sent at least one click to."""
    counts = {}
    for r in rows:
        pub, offer = normalise(r, "affiliate"), normalise(r, "offer")
        if offer["clicks"] > 0:
            counts.setdefault(pub["label"], set()).add(offer["label"])
    return {pub: len(offers) for pub, offers in counts.items()}


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
        "prev_by_offer": [mk(*o, scale=0.91) for o in offers],
        "lastmonth_by_affiliate": [mk(*p, scale=29.4) for p in pubs],
        "lastmonth_by_offer": [mk(*o, scale=30.2) for o in offers],
        "mtd_by_day": mtd,
        "day_campaigns": {p[0]: 4 for p in pubs},
        "prev_campaigns": {p[0]: 3 for p in pubs},
        "lastmonth_campaigns": {p[0]: 9 for p in pubs},
    }


# ------------------------------------------------------------------------ output

def money(v):
    return f"{CURRENCY} {v:,.2f}"


def delta(cur, prev):
    if not prev:
        return '<span style="color:#6b7280">n/a</span>'
    pct = (cur - prev) / prev * 100
    if abs(pct) < 0.05:
        return '<span style="color:#6b7280">– 0.0%</span>'
    color = "#15803d" if pct >= 0 else "#b91c1c"
    arrow = "▲" if pct >= 0 else "▼"
    return f'<span style="color:{color}">{arrow} {abs(pct):.1f}%</span>'


TH = 'style="text-align:{a};padding:8px;border-bottom:2px solid #e5e7eb"'
TD = 'style="text-align:{a};padding:8px;border-bottom:1px solid #f1f5f9{x}"'


def grid(title, head, rows, bold_last=False):
    h = "".join(f'<th {TH.format(a="left" if i == 0 else "right")}>{c}</th>' for i, c in enumerate(head))
    b = ""
    for n, cells in enumerate(rows):
        x = ";font-weight:600" if bold_last and n == len(rows) - 1 else ""
        b += "<tr>" + "".join(f'<td {TD.format(a="left" if i == 0 else "right", x=x)}>{c}</td>'
                              for i, c in enumerate(cells)) + "</tr>"
    if not rows:
        b = f'<tr><td colspan="{len(head)}" style="padding:8px;color:#6b7280">No activity</td></tr>'
    return (f'<h2 style="font-size:16px;margin:28px 0 8px">{title}</h2>'
            f'<table style="width:100%;border-collapse:collapse;font-size:13px">'
            f"<thead><tr>{h}</tr></thead><tbody>{b}</tbody></table>")


def two_day_summary(day, t, p):
    """Metrics as rows, yesterday vs 2 days ago as columns."""
    prev = day - dt.timedelta(days=1)
    head = ["", f"Yesterday<br><small>{day:%a %d %b}</small>", f"2 days ago<br><small>{prev:%a %d %b}</small>", "Change"]
    metrics = [("Income", "income", money), ("Payout", "payout", money), ("Profit", "profit", money),
               ("Conversions", "conversions", lambda v: f"{v:,}"), ("Approved", "approved", lambda v: f"{v:,}"),
               ("Pending", "pending", lambda v: f"{v:,}"), ("Clicks", "clicks", lambda v: f"{v:,}"),
               ("Conversion rate", "cr", lambda v: f"{v:.2f}%"), ("EPC", "epc", money),
               ("Margin", "margin", lambda v: f"{v:.1f}%")]
    return grid("Yesterday vs 2 days ago", head,
                [[name, fmt(t[k]), fmt(p[k]), delta(t[k], p[k])] for name, k, fmt in metrics])


def breakdown(title, first_col, cur, prev, campaigns=None, converted_only=False):
    """One row per publisher/offer with both days side by side.

    campaigns: (yesterday, 2 days ago) dicts of campaign counts per publisher, shown as extra columns.
    converted_only: hide rows with no conversions on either day (totals still include them).
    """
    keys = {r["label"] for r in cur} | {r["label"] for r in prev}
    c = {r["label"]: r for r in cur}
    p = {r["label"]: r for r in prev}
    empty = {"clicks": 0, "conversions": 0, "income": 0.0, "profit": 0.0}
    camp = lambda i, k: [f'{campaigns[0].get(k, 0):,}', f'{campaigns[1].get(k, 0):,}'] if campaigns else []
    rows = []
    for k in sorted(keys, key=lambda k: (c.get(k, empty)["income"], p.get(k, empty)["income"]), reverse=True):
        a, b = c.get(k, empty), p.get(k, empty)
        if converted_only and not (a["conversions"] or b["conversions"]):
            continue
        rows.append([html.escape(k)] + camp(0, k) + [f'{a["conversions"]:,}', f'{b["conversions"]:,}',
                     money(a["income"]), money(b["income"]), delta(a["income"], b["income"]), money(a["profit"])])
    if rows:
        a, b = summarise(cur), summarise(prev)
        tc = [f'{sum(campaigns[0].values()):,}', f'{sum(campaigns[1].values()):,}'] if campaigns else []
        rows.append(["Total"] + tc + [f'{a["conversions"]:,}', f'{b["conversions"]:,}', money(a["income"]),
                     money(b["income"]), delta(a["income"], b["income"]), money(a["profit"])])
    head = [first_col] + (["Campaigns yesterday", "Campaigns 2 days ago"] if campaigns else []) + [
        "Conv. yesterday", "Conv. 2 days ago", "Income yesterday", "Income 2 days ago", "Change", "Profit yesterday"]
    return grid(title, head, rows, bold_last=bool(rows))


def period_table(title, first_col, rows, campaigns=None, converted_only=False):
    """One period: one row per publisher/offer, sorted by income, with a total row.

    campaigns: dict of campaign counts per publisher, shown as an extra column.
    converted_only: hide rows with no conversions (the total still includes them).
    """
    camp = lambda k: [f'{campaigns.get(k, 0):,}'] if campaigns is not None else []
    out = []
    for r in sorted(rows, key=lambda r: r["income"], reverse=True):
        if converted_only and not r["conversions"]:
            continue
        cr = r["conversions"] / r["clicks"] * 100 if r["clicks"] else 0
        out.append([html.escape(r["label"])] + camp(r["label"]) + [f'{r["clicks"]:,}', f'{r["conversions"]:,}',
                    f"{cr:.2f}%", money(r["income"]), money(r["payout"]), money(r["profit"])])
    if out:
        t = summarise(rows)
        tc = [f'{sum(campaigns.values()):,}'] if campaigns is not None else []
        out.append(["Total"] + tc + [f'{t["clicks"]:,}', f'{t["conversions"]:,}', f'{t["cr"]:.2f}%',
                    money(t["income"]), money(t["payout"]), money(t["profit"])])
    head = [first_col] + (["Campaigns"] if campaigns is not None else []) + [
        "Clicks", "Conv.", "CR", "Income", "Payout", "Profit"]
    return grid(title, head, out, bold_last=bool(out))


def kpi(label, value, sub=""):
    return (f'<td style="padding:14px;background:#f8fafc;border:1px solid #e5e7eb;border-radius:8px;width:25%">'
            f'<div style="font-size:12px;color:#6b7280">{label}</div>'
            f'<div style="font-size:20px;font-weight:600;margin-top:4px">{value}</div>'
            f'<div style="font-size:12px;margin-top:2px">{sub}</div></td>')


def render_html(day, data, demo=False):
    t = summarise(data["day_by_affiliate"])
    p = summarise(data["prev_by_affiliate"])
    m = summarise(data["mtd_by_day"])
    lm = summarise(data["lastmonth_by_affiliate"])
    lm_name = f'{day.replace(day=1) - dt.timedelta(days=1):%B %Y}'
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
<p style="color:#6b7280;margin:4px 0 20px">Yesterday {day:%a %d %b %Y} vs 2 days ago {day - dt.timedelta(days=1):%a %d %b %Y} · Source: Affise</p>
<table style="width:100%;border-spacing:8px;margin:0 -8px"><tr>
{kpi("Income yesterday", money(t["income"]), delta(t["income"], p["income"]) + " vs 2 days ago")}
{kpi("Income 2 days ago", money(p["income"]), f'{p["conversions"]:,} conversions')}
{kpi("Profit yesterday", money(t["profit"]), delta(t["profit"], p["profit"]) + " vs 2 days ago")}
{kpi("Conversions yesterday", f'{t["conversions"]:,}', delta(t["conversions"], p["conversions"]) + " vs 2 days ago")}
</tr><tr>
{kpi("Month-to-date income", money(m["income"]), f'1–{day.day} {day:%b}, up to yesterday')}
{kpi("Month-to-date profit", money(m["profit"]), f'{m["margin"]:.1f}% margin')}
{kpi("Month forecast (income)", money(forecast), "run-rate")}
{kpi("MTD conversions", f'{m["conversions"]:,}', f'{m["declined"]} declined')}
</tr></table>
{two_day_summary(day, t, p)}
{breakdown("By publisher", "Publisher", data["day_by_affiliate"], data["prev_by_affiliate"],
           campaigns=(data["day_campaigns"], data["prev_campaigns"]))}
{breakdown("By offer (offers with conversions)", "Offer", data["day_by_offer"], data["prev_by_offer"],
           converted_only=True)}
<h2 style="font-size:18px;margin:36px 0 4px;padding-top:16px;border-top:1px solid #e5e7eb">Last month — {lm_name}</h2>
<table style="width:100%;border-spacing:8px;margin:0 -8px"><tr>
{kpi("Income", money(lm["income"]), f'{lm["approved"]:,} approved · {lm["pending"]:,} pending')}
{kpi("Payout", money(lm["payout"]), "publisher share")}
{kpi("Profit", money(lm["profit"]), f'{lm["margin"]:.1f}% margin')}
{kpi("Conversions", f'{lm["conversions"]:,}', f'{lm["clicks"]:,} clicks · CR {lm["cr"]:.2f}%')}
</tr></table>
{period_table(f"{lm_name} by publisher", "Publisher", data["lastmonth_by_affiliate"],
              campaigns=data["lastmonth_campaigns"])}
{period_table(f"{lm_name} by offer (offers with conversions)", "Offer", data["lastmonth_by_offer"],
              converted_only=True)}
<h2 style="font-size:16px;margin:28px 0 8px">Month-to-date daily income</h2>
<table style="width:100%;border-collapse:collapse">{trend}</table>
<p style="font-size:11px;color:#9ca3af;margin-top:28px">Income = amount networks pay us (Affise "charge"). Payout = publisher share
(Affise "revenue"). Profit = Income − Payout. Includes pending conversions, which may still be declined by the network.
Campaigns = offers a publisher sent at least one click to that day (or month). Offer tables list only offers with conversions; totals include all offers.</p>
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
    if day >= dt.date.today():
        sys.exit("The report covers complete days only: pass yesterday or earlier.")
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
