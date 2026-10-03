#!/usr/bin/env python3
"""Bulls offer selection: which affiliate offers are worth testing with our own ad budget.

Reads an offer list (CSV, one row per offer per network) and, optionally, the Bulls test log,
and writes an HTML report with four sections:
  1. Qualified offers      (search volume >= 200,000, best source per brand, economics, score)
  2. Missing information   (what must be checked before testing)
  3. Top candidates        (top 10 by score)
  4. Recommended tests     (best 3-5 READY TO TEST offers, budget, max clicks, stop rules)
plus test control and learnings when a test log is given.

Nothing is launched. The script never guesses: an empty cell stays NOT VERIFIED.

Usage:
  python3 select_offers.py offers.csv                     # offers only
  python3 select_offers.py offers.csv --tests tests.csv   # + test control and learnings
  python3 select_offers.py --demo                         # sample data

Stdlib only, so it runs anywhere Python 3.9+ is available.
"""

import argparse
import csv
import datetime as dt
import html
import math
import os
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.environ.get("BULLS_OUT_DIR", os.path.join(HERE, "output"))

NV = "NOT VERIFIED"
CPC_NA = "CPC NOT AVAILABLE"
AOV_REQ = "AOV REQUIRED"
CR_SCENARIOS = (0.005, 0.01, 0.02, 0.03)
PERCENT_TYPES = {"CPS%", "REVSHARE", "REV SHARE", "PERCENT", "%"}
STATUS_ORDER = {"READY TO TEST": 0, "NEEDS REVIEW": 1, "MISSING DATA": 2, "DO NOT TEST": 3}
FAILED_RESULTS = {"FAILED", "LOSS", "STOP", "STOPPED", "NOT PROFITABLE", "ZERO CONVERSIONS"}


# --------------------------------------------------------------------------- parsing

def clean(v):
    return (v or "").strip()


def num(v):
    """A number from a cell, or None. Use a dot for decimals: 0.35, 1200000 or 1,200,000."""
    s = clean(v)
    for ch in "$€£₪%, ":
        s = s.replace(ch, "")
    try:
        return float(s) if s else None
    except ValueError:
        return None


def yes_no(v):
    s = clean(v).lower()
    if s in ("yes", "y", "true", "allowed", "1"):
        return "Yes"
    if s in ("no", "n", "false", "not allowed", "prohibited", "forbidden", "0"):
        return "No"
    return NV


def level(v):
    s = clean(v).upper()
    return s if s in ("HIGH", "MEDIUM", "LOW") else NV


def date(v):
    try:
        return dt.date.fromisoformat(clean(v))
    except ValueError:
        return None


def read_csv(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        return [{(k or "").strip().lower(): (v or "") for k, v in row.items()}
                for row in csv.DictReader(f) if any(clean(v) for v in row.values())]


def text_or_nv(v):
    return clean(v) or NV


# --------------------------------------------------------------------------- one source (offer row)

def build_source(row):
    """One offer in one network. Works out the real payout: what reaches us after any network share."""
    raw_payout = clean(row.get("payout_value"))
    ptype = clean(row.get("payout_type")).upper()
    s = {
        "brand": clean(row.get("brand")),
        "category": clean(row.get("category")),
        "network": text_or_nv(row.get("network")),
        "account": text_or_nv(row.get("network_account")),
        "geo": clean(row.get("geo")).upper() or NV,
        "payout_type": ptype or NV,
        "payout_raw": raw_payout or NV,
        "currency": clean(row.get("payout_currency")).upper() or NV,
        "offer_status": text_or_nv(row.get("offer_status")),
        "approval": text_or_nv(row.get("approval_status")),
        "link": text_or_nv(row.get("affiliate_link")),
        "paid_search": yes_no(row.get("paid_search_allowed")),
        "brand_bidding": yes_no(row.get("brand_bidding_allowed")),
        "direct_linking": yes_no(row.get("direct_linking_allowed")),
        "restrictions": clean(row.get("other_restrictions")),
        "cookie_days": num(row.get("cookie_days")),
        "tracking": level(row.get("tracking_reliability")),
        "reconcilable": yes_no(row.get("conversions_reconcilable")),
        "share_pct": num(row.get("network_share_pct")),
        "aov": num(row.get("verified_aov")),
        "notes": clean(row.get("notes")),
        "row": row,
    }
    value = num(raw_payout)
    s["is_percent"] = "%" in raw_payout or ptype in PERCENT_TYPES
    s["gross"] = s["real"] = None
    s["payout_issue"] = ""
    if value is None:
        s["payout_issue"] = "payout value NOT VERIFIED"
    elif s["is_percent"]:
        if s["aov"] is None:
            s["payout_issue"] = AOV_REQ
        else:
            s["gross"] = value / 100 * s["aov"]
    else:
        s["gross"] = value
    if s["gross"] is not None:
        if s["share_pct"] is None:
            s["payout_issue"] = "network share NOT VERIFIED (enter 0 if the payout shown is already ours)"
        else:
            s["real"] = s["gross"] * (1 - s["share_pct"] / 100)

    status = s["offer_status"].lower()
    approval = s["approval"].lower()
    s["blockers"] = []
    if s["offer_status"] != NV and status != "active":
        s["blockers"].append(f"offer status is {s['offer_status']}")
    if approval in ("rejected", "declined"):
        s["blockers"].append("our application was rejected")
    if s["paid_search"] == "No":
        s["blockers"].append("paid search not allowed")
    if s["brand_bidding"] == "No":
        s["blockers"].append("brand bidding not allowed")
    s["unclear"] = [label for label, ok in (
        ("offer status", s["offer_status"] != NV),
        ("approval", approval == "approved"),
        ("paid search", s["paid_search"] == "Yes"),
        ("brand bidding", s["brand_bidding"] == "Yes"),
        ("direct linking", s["direct_linking"] != NV),
        ("tracking", s["tracking"] != NV),
        ("real payout", s["real"] is not None),
    ) if not ok]
    # 0 = usable now, 1 = usable once checks are done, 2 = blocked
    s["tier"] = 2 if s["blockers"] else (1 if s["unclear"] else 0)
    return s


def source_label(s):
    return s["network"] + (f" ({s['account']})" if s["account"] != NV else "")


def pick_best(sources):
    """Best REAL source: usable before blocked, then highest real payout, then tracking and cookie window."""
    track = {"HIGH": 0, "MEDIUM": 1, "LOW": 2, NV: 3}
    ranked = sorted(sources, key=lambda s: (
        s["tier"], s["real"] is None, -(s["real"] or 0), track[s["tracking"]], -(s["cookie_days"] or 0)))
    best = ranked[0]
    why = []
    if best["real"] is not None:
        share = f" after a {best['share_pct']:g}% network share" if best["share_pct"] else ""
        why.append(f"real payout {money(best['real'], best['currency'])}{share}")
    if best["tier"] == 0:
        why.append("active, approved and paid search + brand bidding allowed")
    elif best["tier"] == 1:
        why.append("still to check: " + ", ".join(best["unclear"]))
    else:
        why.append("every source has a blocker: " + "; ".join(best["blockers"]))
    alts = []
    for s in ranked[1:]:
        payout = money(s["real"], s["currency"]) if s["real"] is not None else (s["payout_issue"] or NV)
        gross = (f", shows {money(s['gross'], s['currency'])} before share"
                 if s["gross"] and s["real"] is not None and s["gross"] > s["real"] else "")
        reason = ("blocked: " + "; ".join(s["blockers"]) if s["blockers"] else
                  "unclear: " + ", ".join(s["unclear"]) if s["unclear"] else "usable")
        alts.append(f"{source_label(s)}: real {payout}{gross} ({reason})")
        if (s["real"] or 0) > (best["real"] or 0) and s["tier"] > best["tier"] and not s["blockers"]:
            why.append(f"{source_label(s)} pays more ({money(s['real'], s['currency'])}) but is not cleared yet; "
                       "worth checking")
    return best, "; ".join(why), alts


# --------------------------------------------------------------------------- one brand (all its sources)

def first(rows, key):
    """Brand-level value (search volume, CPC, intent…) from the first row that has it, plus a conflict note."""
    vals = [clean(r.get(key)) for r in rows if clean(r.get(key))]
    conflict = len({v.lower() for v in vals}) > 1
    return (vals[0] if vals else ""), conflict


def money(v, cur=""):
    if v is None:
        return NV
    cur = "" if cur in ("", NV) else cur
    sym = {"USD": "$", "EUR": "€", "GBP": "£"}.get(cur)
    v = round(v, 2) + 0.0
    body = f"{abs(v):,.2f}"
    sign = "−" if v < 0 else ""
    return f"{sign}{sym}{body}" if sym else f"{sign}{body} {cur}".strip()


def pct(v, digits=2):
    return NV if v is None else f"{v * 100:.{digits}f}%"


def evaluate(key, rows, cfg, history):
    sources = [build_source(r) for r in rows]
    best, why, alts = pick_best(sources)
    o = {"key": key, "brand": best["brand"], "geo": best["geo"], "sources": sources, "best": best,
         "why_source": why, "alternatives": alts, "missing": [], "review": [], "block": [], "notes": []}

    for field in ("category", "keyword", "search_volume", "search_volume_source", "cpc", "cpc_currency",
                  "cpc_source", "cpc_date", "commercial_intent", "intent_reason"):
        o[field], conflict = first(rows, field)
        if conflict and field in ("search_volume", "cpc", "commercial_intent", "keyword"):
            o["notes"].append(f"rows disagree on {field.replace('_', ' ')}; used {o[field]!r}, please check")
    o["sv"] = num(o["search_volume"])
    o["cpc_value"] = num(o["cpc"])
    o["cpc_cur"] = clean(o["cpc_currency"]).upper() or NV
    o["intent"] = level(o["commercial_intent"])
    o["cpc_dt"] = date(o["cpc_date"])
    o["real"] = best["real"]

    # ---- search volume filter
    if o["sv"] is None:
        o["missing"].append("monthly search volume (and the keyword used)")
        o["qualified"] = None
    else:
        o["qualified"] = o["sv"] >= cfg.min_volume
        if not clean(o["keyword"]):
            o["review"].append("keyword behind the search volume not recorded")

    # ---- economics
    o["be"] = None
    o["rpc"] = {}
    o["margin"] = {}
    if o["cpc_value"] is None:
        o["missing"].append(CPC_NA + " (record CPC, currency, source and date)")
    if best["real"] is None:
        o["missing"].append(f"real payout: {best['payout_issue'] or NV}")
    currencies_ok = o["cpc_cur"] == best["currency"] and best["currency"] != NV
    if o["cpc_value"] is not None and best["real"] is not None and not currencies_ok:
        o["missing"].append(f"CPC currency ({o['cpc_cur']}) and payout currency ({best['currency']}) must match; "
                            "not converted, to avoid inventing an exchange rate")
    if o["cpc_value"] is not None and best["real"] and currencies_ok:
        o["be"] = o["cpc_value"] / best["real"]
        for cr in CR_SCENARIOS:
            o["rpc"][cr] = best["real"] * cr
            o["margin"][cr] = best["real"] * cr - o["cpc_value"]
    if o["cpc_value"] is not None:
        if not o["cpc_dt"]:
            o["review"].append("CPC date not recorded")
        elif (cfg.today - o["cpc_dt"]).days > cfg.max_cpc_age:
            o["review"].append(f"CPC checked {(cfg.today - o['cpc_dt']).days} days ago; re-check it")
        if not clean(o["cpc_source"]):
            o["review"].append("CPC source not recorded")

    # ---- intent
    if o["intent"] == NV:
        o["missing"].append("commercial intent (HIGH / MEDIUM / LOW with a short reason)")
    elif o["intent"] == "LOW":
        o["review"].append("LOW commercial intent: big volume, weak buying intent")

    # ---- permissions, status, tracking (from the chosen source)
    o["block"].extend(best["blockers"])
    for label, val in (("paid search allowed?", best["paid_search"]), ("brand bidding allowed?", best["brand_bidding"]),
                       ("direct linking allowed?", best["direct_linking"])):
        if val == NV:
            o["missing"].append(label)
    if best["direct_linking"] == "No":
        o["notes"].append("no direct linking: needs our own landing page")
    if best["offer_status"] == NV:
        o["missing"].append("offer status (active?)")
    if best["approval"] == NV:
        o["missing"].append("approval status")
    elif best["approval"].lower() not in ("approved", "rejected", "declined"):
        o["review"].append(f"approval is {best['approval']}, not approved yet")
    if best["link"] == NV:
        o["missing"].append("affiliate link")
    if best["tracking"] == NV:
        o["missing"].append("tracking reliability (HIGH / MEDIUM / LOW)")
    elif best["tracking"] == "LOW":
        o["review"].append("tracking reliability is LOW")
    if best["reconcilable"] == NV:
        o["missing"].append("can conversions be reconciled with the network?")
    elif best["reconcilable"] == "No":
        o["review"].append("conversions cannot be reconciled with the network")
    if best["restrictions"]:
        o["review"].append(f"restrictions to read before launch: {best['restrictions']}")

    if o["be"] is not None:
        if o["be"] > CR_SCENARIOS[-1]:
            o["block"].append(f"break-even CR {pct(o['be'])} is above 3%: loses money in every scenario "
                              "unless payout goes up or CPC comes down")
        elif o["be"] > 0.02:
            o["review"].append(f"break-even CR {pct(o['be'])} needs a strong conversion rate")

    # ---- previous tests
    o["history"] = history.get(key, []) or history.get((key[0], ""), [])
    for t in o["history"]:
        res = (t["result"] or t["status"]).upper()
        if t["status"].upper() == "TESTING":
            o["review"].append(f"already in test since {t['launch_date'] or '?'}")
        elif res in FAILED_RESULTS or (t["spend"] and not t["conversions"]):
            o["review"].append(f"tested before ({t['launch_date'] or '?'}): {res or 'no conversions'}"
                               f"{' — ' + t['why'] if t['why'] else ''}. Needs a new reason to retest")
        else:
            o["notes"].append(f"previous test ({t['launch_date'] or '?'}): {res}, ROAS {pct(t['roas'], 0)}")

    o["score"], o["points"] = score(o, best)
    o["confidence"] = confidence(o, best)
    if o["block"] or o["qualified"] is False:
        o["status"] = "DO NOT TEST"
    elif o["missing"]:
        o["status"] = "MISSING DATA"
    elif o["review"]:
        o["status"] = "NEEDS REVIEW"
    else:
        o["status"] = "READY TO TEST"
    return o


def score(o, best):
    """0-100. Missing data scores zero for that part: nothing is assumed."""
    p = {}
    sv = o["sv"] or 0
    p["Search volume"] = 20 if sv >= 2_000_000 else 17 if sv >= 1_000_000 else 14 if sv >= 500_000 else 10 if sv >= 200_000 else 0
    be = o["be"]
    p["Payout / economics"] = (0 if be is None else 25 if be <= 0.005 else 20 if be <= 0.01 else
                               15 if be <= 0.015 else 10 if be <= 0.02 else 5 if be <= 0.03 else 0)
    c = o["cpc_value"]
    p["CPC"] = (0 if c is None else 20 if c <= 0.3 else 16 if c <= 0.6 else 12 if c <= 1 else
                8 if c <= 2 else 4 if c <= 4 else 0)
    p["Commercial intent"] = {"HIGH": 20, "MEDIUM": 10}.get(o["intent"], 0)
    p["Traffic permissions"] = ((4 if best["paid_search"] == "Yes" else 0) + (4 if best["brand_bidding"] == "Yes" else 0)
                                + (2 if best["direct_linking"] == "Yes" else 0))
    p["Tracking / source"] = ({"HIGH": 3, "MEDIUM": 2}.get(best["tracking"], 0)
                              + (2 if best["reconcilable"] == "Yes" else 0))
    return sum(p.values()), p


def confidence(o, best):
    critical = [o["sv"] is not None, best["real"] is not None, o["cpc_value"] is not None, o["intent"] != NV,
                best["paid_search"] != NV, best["brand_bidding"] != NV, best["direct_linking"] != NV,
                best["tracking"] != NV, best["reconcilable"] != NV, best["offer_status"] != NV,
                best["approval"] != NV]
    gaps = critical.count(False)
    if o["be"] is None or gaps >= 3:
        conf = "LOW"
    elif gaps:
        conf = "MEDIUM"
    else:
        conf = "HIGH"
    stale = any("days ago" in r or "CPC date" in r for r in o["review"])
    if stale and conf != "LOW":
        conf = "MEDIUM" if conf == "HIGH" else "LOW"
    return conf


# --------------------------------------------------------------------------- test plan

def test_plan(o, cfg):
    """Budget = enough clicks to expect 3 conversions at break-even CR (= about 3 payouts), capped by the max budget.

    If the offer truly converts at break-even, the chance of 0 conversions after that many clicks is about 5%,
    so 0 conversions at the limit is a clear 'this does not work at this CPC' signal.
    """
    cpc, be, payout, cur = o["cpc_value"], o["be"], o["real"], o["best"]["currency"]
    clicks = math.ceil(cfg.signal_conversions / be)
    budget = clicks * cpc
    capped = budget > cfg.max_budget
    if capped:
        budget = cfg.max_budget
        clicks = math.floor(budget / cpc)
    expected = clicks * be
    good, risk = [], []
    if o["be"] <= 0.01:
        good.append(f"breaks even at only {pct(be)} CR")
    else:
        good.append(f"breaks even at {pct(be)} CR")
    if o["intent"] == "HIGH":
        good.append("HIGH purchase intent")
    good.append(f"{o['sv']:,.0f} monthly searches")
    if payout >= 50:
        good.append(f"strong real payout {money(payout, cur)}")
    if o["best"]["tracking"] == "HIGH":
        good.append("reliable tracking")
    if o["be"] > 0.015:
        risk.append(f"needs {pct(be)} CR just to break even")
    if o["intent"] == "MEDIUM":
        risk.append("MEDIUM intent: many searches may be informational")
    if o["best"]["direct_linking"] == "No":
        risk.append("needs a landing page (no direct linking)")
    if o["best"]["tracking"] == "MEDIUM":
        risk.append("tracking only MEDIUM: test the link before spending")
    if o["best"]["cookie_days"] is not None and o["best"]["cookie_days"] < 7:
        risk.append(f"short cookie window ({o['best']['cookie_days']:g} days)")
    if o["best"]["restrictions"]:
        risk.append(f"restrictions: {o['best']['restrictions']}")
    if o["sv"] >= 1_000_000 and o["cpc_value"] >= 1:
        risk.append("competitive brand keyword: CPC may climb above plan")
    if capped:
        risk.append(f"budget capped at {money(cfg.max_budget, cur)}: only ~{expected:.1f} conversions expected at "
                    "break-even, so a 0 result is a weaker signal")
    if not risk:
        risk.append("real CR is unknown until tested; brand CPC can rise once we bid")
    return {
        "why": "; ".join(good),
        "risk": "; ".join(risk),
        "budget": budget,
        "clicks": clicks,
        "expected": expected,
        "checkpoint": clicks // 2,
        "cpc_limit": cpc * cfg.cpc_tolerance,
        "scale": (f"at least {cfg.scale_conversions} conversions and ROAS of {cfg.scale_roas:.0%} or more "
                  f"(CR of {pct(be * cfg.scale_roas)} or better) with conversions confirmed by the network"),
    }


# --------------------------------------------------------------------------- test log

def load_tests(path, cfg):
    tests = []
    for r in read_csv(path):
        t = {k: clean(r.get(k)) for k in ("test_id", "brand", "category", "geo", "launch_date", "traffic_source",
                                          "ad_account", "offer_source", "network_account", "payout_currency",
                                          "commercial_intent", "status", "result", "why")}
        for k in ("payout", "planned_cpc", "test_budget", "max_clicks", "search_volume", "clicks", "spend",
                  "conversions", "revenue"):
            t[k] = num(r.get(k))
        t["tracking_working"] = yes_no(r.get("tracking_working"))
        t["offer_still_active"] = yes_no(r.get("offer_still_active"))
        t["terms_changed"] = yes_no(r.get("terms_changed"))
        clicks, spend, conv, rev = t["clicks"] or 0, t["spend"] or 0, t["conversions"] or 0, t["revenue"] or 0
        t["cpc"] = spend / clicks if clicks else None
        t["cr"] = conv / clicks if clicks else None
        t["roas"] = rev / spend if spend else None
        t["profit"] = rev - spend
        t["suggested"], t["reason"] = suggest(t, cfg)
        tests.append(t)
    return tests


def suggest(t, cfg):
    """Apply the stop rules. Suggestion only: the person running the test decides."""
    clicks, spend, conv = t["clicks"] or 0, t["spend"] or 0, t["conversions"] or 0
    budget, max_clicks = t["test_budget"], t["max_clicks"]
    if t["status"].upper() in ("STOP", "SCALE"):
        return t["status"].upper(), "decided"
    if t["tracking_working"] == "No":
        return "PAUSE", "tracking is not working"
    if t["offer_still_active"] == "No":
        return "STOP", "offer is no longer active"
    if t["terms_changed"] == "Yes":
        return "PAUSE", "offer terms changed: re-check payout and traffic rules"
    if t["cpc"] and t["planned_cpc"] and t["cpc"] > t["planned_cpc"] * cfg.cpc_tolerance:
        return "PAUSE", f"CPC {t['cpc']:.2f} is more than {cfg.cpc_tolerance - 1:.0%} above plan ({t['planned_cpc']:.2f})"
    done = (budget and spend >= budget) or (max_clicks and clicks >= max_clicks)
    if done:
        if conv == 0:
            return "REVIEW", "test limit reached with 0 conversions: do not relaunch without a new reason"
        if conv >= cfg.scale_conversions and (t["roas"] or 0) >= cfg.scale_roas:
            return "SCALE", f"{conv:g} conversions, ROAS {t['roas']:.0%}"
        if (t["roas"] or 0) >= 1:
            return "REVIEW", f"profitable but below the scale rule (ROAS {t['roas']:.0%}, {conv:g} conversions)"
        return "STOP", f"test limit reached, ROAS {t['roas']:.0%}"
    half = (budget and spend >= budget / 2) or (max_clicks and clicks >= max_clicks / 2)
    if half and conv == 0:
        return "REVIEW", "halfway with 0 conversions: check tracking and search terms before spending more"
    if not budget and not max_clicks:
        return "REVIEW", "no test budget or click limit set: set one before spending more"
    return "TESTING", "within limits"


def band(v, edges, unit=""):
    if v is None:
        return NV
    for lo, hi in zip(edges, edges[1:]):
        if lo <= v < hi:
            return f"{lo:g}{unit}–{hi:g}{unit}"
    return f"{edges[-1]:g}{unit}+"


def learnings(tests):
    """Group finished tests by category, GEO, network, intent, CPC, payout and search volume range."""
    done = [t for t in tests if (t["spend"] or 0) > 0 and t["status"].upper() != "TESTING"]
    dims = [
        ("Category", lambda t: t["category"] or NV),
        ("GEO", lambda t: t["geo"] or NV),
        ("Network", lambda t: t["offer_source"] or NV),
        ("Commercial intent", lambda t: t["commercial_intent"].upper() or NV),
        ("CPC range", lambda t: band(t["planned_cpc"], [0, 0.3, 0.6, 1, 2])),
        ("Payout range", lambda t: band(t["payout"], [0, 20, 50, 100, 200])),
        ("Search volume", lambda t: band((t["search_volume"] or 0) / 1000 if t["search_volume"] else None,
                                          [200, 500, 1000, 2000], "k")),
    ]
    out = []
    for name, fn in dims:
        groups = defaultdict(list)
        for t in done:
            groups[fn(t)].append(t)
        rows = []
        for label, ts in groups.items():
            spend = sum(t["spend"] or 0 for t in ts)
            rev = sum(t["revenue"] or 0 for t in ts)
            clicks = sum(t["clicks"] or 0 for t in ts)
            conv = sum(t["conversions"] or 0 for t in ts)
            rows.append({"label": label, "tests": len(ts), "wins": sum(1 for t in ts if t["profit"] > 0),
                         "spend": spend, "revenue": rev, "roas": rev / spend if spend else None,
                         "cr": conv / clicks if clicks else None})
        rows.sort(key=lambda r: (r["roas"] or 0), reverse=True)
        out.append((name, rows))
    return done, out


# --------------------------------------------------------------------------- HTML

TH = 'style="text-align:{a};padding:6px 8px;border-bottom:2px solid #e5e7eb;font-size:12px;color:#374151;vertical-align:bottom"'
TD = 'style="text-align:{a};padding:6px 8px;border-bottom:1px solid #f1f5f9;vertical-align:top{x}"'
BADGE = {"READY TO TEST": "#dcfce7;color:#166534", "NEEDS REVIEW": "#fef3c7;color:#92400e",
         "MISSING DATA": "#e0e7ff;color:#3730a3", "DO NOT TEST": "#fee2e2;color:#991b1b",
         "TESTING": "#e0f2fe;color:#075985", "SCALE": "#dcfce7;color:#166534", "PAUSE": "#fef3c7;color:#92400e",
         "STOP": "#fee2e2;color:#991b1b", "REVIEW": "#ede9fe;color:#5b21b6",
         "HIGH": "#dcfce7;color:#166534", "MEDIUM": "#fef3c7;color:#92400e", "LOW": "#fee2e2;color:#991b1b"}


def badge(text):
    style = BADGE.get(text, "#f1f5f9;color:#475569")
    return (f'<span style="background:{style};padding:2px 6px;border-radius:4px;font-size:11px;'
            f'font-weight:600;white-space:nowrap">{html.escape(text)}</span>')


def e(v):
    return html.escape(str(v))


def nv(v):
    """Show NOT VERIFIED in a muted red so gaps stand out."""
    if v == NV or v in (CPC_NA, AOV_REQ):
        return f'<span style="color:#b91c1c;font-size:11px">{e(v)}</span>'
    return e(v)


def grid(head, rows, left=1):
    h = "".join(f'<th {TH.format(a="left" if i < left else "right")}>{c}</th>' for i, c in enumerate(head))
    b = "".join("<tr>" + "".join(f'<td {TD.format(a="left" if i < left else "right", x="")}>{c}</td>'
                                 for i, c in enumerate(r)) + "</tr>" for r in rows)
    if not rows:
        b = f'<tr><td colspan="{len(head)}" style="padding:8px;color:#6b7280">None</td></tr>'
    return (f'<div style="overflow-x:auto"><table style="width:100%;border-collapse:collapse;font-size:12px">'
            f"<thead><tr>{h}</tr></thead><tbody>{b}</tbody></table></div>")


def h2(n, title, sub=""):
    return (f'<h2 style="font-size:18px;margin:40px 0 4px;padding-top:16px;border-top:1px solid #e5e7eb">'
            f'{n}. {title}</h2><p style="color:#6b7280;margin:0 0 12px;font-size:13px">{sub}</p>')


def margin_cell(o, cr):
    m = o["margin"].get(cr)
    if m is None:
        return nv(AOV_REQ if o["best"]["payout_issue"] == AOV_REQ else NV)
    color = "#166534" if m > 0.0005 else "#991b1b" if m < -0.0005 else "#374151"
    return f'<span style="color:{color}">{money(m, o["best"]["currency"])}</span>'


def payout_cell(o):
    b = o["best"]
    if b["real"] is None:
        return nv(AOV_REQ if b["payout_issue"] == AOV_REQ else NV)
    gross = b["payout_raw"] if b["is_percent"] else money(b["gross"], b["currency"])
    extra = f'<br><small style="color:#6b7280">{e(gross)} gross</small>' if b["gross"] != b["real"] or b["is_percent"] else ""
    return money(b["real"], b["currency"]) + extra


def cpc_cell(o):
    if o["cpc_value"] is None:
        return nv(CPC_NA)
    when = clean(o["cpc_date"])
    return money(o["cpc_value"], o["cpc_cur"]) + (f'<br><small style="color:#6b7280">{e(when)}</small>' if when else "")


def qualified_table(offers):
    head = ["Brand", "Network", "Account", "GEO", "Search vol.", "Real payout", "Payout type", "CPC", "Intent",
            "Paid search", "Brand bid", "Direct link", "Break-even CR", "Margin/click @1%", "Margin/click @2%",
            "Score", "Confidence", "Status", "Notes"]
    rows = []
    for o in offers:
        b = o["best"]
        notes = o["block"] + o["review"] + o["notes"]
        if o["missing"]:
            notes = [f"{len(o['missing'])} item(s) missing, see section 2"] + notes
        rows.append([
            f"<b>{e(o['brand'])}</b><br><small style='color:#6b7280'>{e(o['category'])}</small>",
            nv(b["network"]), nv(b["account"]), nv(o["geo"]), f"{o['sv']:,.0f}", payout_cell(o), nv(b["payout_type"]),
            cpc_cell(o), badge(o["intent"]) if o["intent"] != NV else nv(NV), nv(b["paid_search"]),
            nv(b["brand_bidding"]), nv(b["direct_linking"]), f"<b>{pct(o['be'])}</b>" if o["be"] is not None else nv(NV),
            margin_cell(o, 0.01), margin_cell(o, 0.02), f"<b>{o['score']}</b>", badge(o["confidence"]),
            badge(o["status"]), '<small style="display:block;min-width:220px">' + "<br>".join(e(n) for n in notes) + "</small>",
        ])
    return grid(head, rows, left=4)


def economics_table(offers):
    head = ["Brand", "GEO", "Real payout", "CPC"] + [f"Revenue/click @{c * 100:g}%" for c in CR_SCENARIOS] + \
           [f"Margin/click @{c * 100:g}%" for c in CR_SCENARIOS] + ["Break-even CR"]
    rows = []
    for o in offers:
        cur = o["best"]["currency"]
        rows.append([e(o["brand"]), nv(o["geo"]), payout_cell(o), cpc_cell(o)]
                    + [money(o["rpc"][c], cur) if c in o["rpc"] else nv(NV) for c in CR_SCENARIOS]
                    + [margin_cell(o, c) for c in CR_SCENARIOS]
                    + [f"<b>{pct(o['be'])}</b>" if o["be"] is not None else nv(NV)])
    return grid(head, rows, left=2)


def missing_section(offers, unknown_sv):
    items = []
    for o in offers + unknown_sv:
        if not (o["missing"] or o["review"] or o["block"]):
            continue
        li = "".join(f'<li style="color:#991b1b">Blocker: {e(b)}</li>' for b in o["block"])
        li += "".join(f"<li>{e(m)}</li>" for m in o["missing"])
        li += "".join(f'<li style="color:#92400e">{e(r)}</li>' for r in o["review"])
        items.append(f'<div style="margin:0 0 14px"><b>{e(o["brand"])}</b> · {e(o["geo"])} · '
                     f'{e(source_label(o["best"]))} {badge(o["status"])}'
                     f'<ul style="margin:4px 0 0 18px;padding:0;font-size:13px">{li}</ul></div>')
    if not items:
        return '<p style="font-size:13px">Nothing missing.</p>'
    return ('<p style="font-size:12px;color:#6b7280">Red = blocker. Black = data we do not have yet. '
            'Amber = we have it, but someone must look at it before testing.</p>' + "".join(items))


def top_section(top):
    rows = []
    for i, o in enumerate(top, 1):
        pts = ", ".join(f"{k} {v}" for k, v in o["points"].items())
        alts = "<br>".join(e(a) for a in o["alternatives"]) or "only one source"
        rows.append([f"{i}", f"<b>{e(o['brand'])}</b><br><small>{e(o['geo'])}</small>",
                     f"<b>{o['score']}</b><br><small style='color:#6b7280'>{e(pts)}</small>", badge(o["confidence"]),
                     badge(o["status"]), pct(o["be"]) if o["be"] is not None else nv(NV),
                     f"<b>{e(source_label(o['best']))}</b> · {payout_cell(o)}<br><small>{e(o['why_source'])}</small>",
                     f"<small style='color:#6b7280'>{alts}</small>"])
    return grid(["#", "Brand", "Score (breakdown)", "Confidence", "Status", "Break-even CR", "Best source and why",
                 "Other sources"], rows, left=8)


def test_cards(picks, cfg):
    if not picks:
        return ('<p style="font-size:13px;background:#fef3c7;padding:10px;border-radius:6px">No offer is READY TO TEST '
                f"with a score of {cfg.min_score} or more. Clear the items in section 2 for the top candidates first. "
                "Nothing should be launched yet.</p>")
    cards = []
    for i, (o, p) in enumerate(picks, 1):
        cur = o["best"]["currency"]
        cards.append(f"""<div style="border:1px solid #e5e7eb;border-radius:8px;padding:14px 16px;margin:0 0 14px">
<div style="font-size:15px;font-weight:600">Test {i}: {e(o['brand'])} · {e(o['geo'])} · via {e(source_label(o['best']))}
<span style="float:right">score {o['score']} {badge(o['confidence'])}</span></div>
<table style="font-size:13px;margin-top:8px;border-collapse:collapse;width:100%">
<tr><td style="padding:3px 12px 3px 0;color:#6b7280;width:190px">Why it is interesting</td><td>{e(p['why'])}</td></tr>
<tr><td style="padding:3px 12px 3px 0;color:#6b7280">Main risk</td><td>{e(p['risk'])}</td></tr>
<tr><td style="padding:3px 12px 3px 0;color:#6b7280">Payout / CPC</td><td>{money(o['real'], cur)} real payout · {money(o['cpc_value'], o['cpc_cur'])} CPC (planned)</td></tr>
<tr><td style="padding:3px 12px 3px 0;color:#6b7280">Break-even CR</td><td><b>{pct(o['be'])}</b> (1 sale every {1 / o['be']:,.0f} clicks)</td></tr>
<tr><td style="padding:3px 12px 3px 0;color:#6b7280">Initial budget</td><td><b>{money(p['budget'], cur)}</b></td></tr>
<tr><td style="padding:3px 12px 3px 0;color:#6b7280">Maximum clicks</td><td><b>{p['clicks']:,}</b> (≈{p['expected']:.1f} conversions expected if it just breaks even)</td></tr>
<tr><td style="padding:3px 12px 3px 0;color:#6b7280;vertical-align:top">Stop / pause if</td><td><ul style="margin:0;padding-left:18px">
<li>spend reaches {money(p['budget'], cur)} or clicks reach {p['clicks']:,}</li>
<li>0 conversions after {p['checkpoint']:,} clicks (halfway): pause and check tracking and search terms</li>
<li>actual CPC goes above {money(p['cpc_limit'], o['cpc_cur'])}</li>
<li>tracking is not working (send a test click/conversion before launch), offer terms change, or the offer goes inactive</li>
</ul></td></tr>
<tr><td style="padding:3px 12px 3px 0;color:#6b7280">Scale only if</td><td>{e(p['scale'])}</td></tr>
</table></div>""")
    return "".join(cards)


def tests_section(tests, done, groups, cfg):
    if not tests:
        return ""
    rows = []
    for t in tests:
        cur = t["payout_currency"]
        rows.append([e(t["brand"]), e(t["launch_date"]), e(t["traffic_source"]), e(t["ad_account"]), e(t["offer_source"]),
                     money(t["payout"], cur), money(t["planned_cpc"], cur), money(t["test_budget"], cur),
                     f"{t['clicks'] or 0:,.0f}", money(t["spend"] or 0, cur), f"{t['conversions'] or 0:g}",
                     money(t["revenue"] or 0, cur), pct(t["roas"], 0), pct(t["cr"]), badge(t["status"].upper() or NV),
                     badge(t["suggested"]) + f"<br><small>{e(t['reason'])}</small>"])
    out = h2(5, "Test control", "Every Bulls test, with the stop rules applied. The suggestion never changes anything; "
             "you decide.")
    out += grid(["Brand", "Launch", "Traffic source", "Ad account", "Offer source", "Payout", "Planned CPC", "Budget",
                 "Clicks", "Spend", "Conv.", "Revenue", "ROAS", "CR", "Status", "Stop-rule check"], rows)
    out += h2(6, "Learning from results", f"{len(done)} finished test(s). A group with fewer than 3 tests is a hint, "
              "not a pattern yet.")
    for name, rows in groups:
        out += f'<h3 style="font-size:14px;margin:18px 0 6px">By {name.lower()}</h3>'
        out += grid([name, "Tests", "Profitable", "Spend", "Revenue", "ROAS", "CR"],
                    [[e(r["label"]), r["tests"], r["wins"], money(r["spend"]), money(r["revenue"]), pct(r["roas"], 0),
                      pct(r["cr"])] for r in rows])
    lessons = [t for t in done if t["why"]]
    if lessons:
        out += '<h3 style="font-size:14px;margin:18px 0 6px">Why tests worked or failed</h3><ul style="font-size:13px">'
        out += "".join(f"<li><b>{e(t['brand'])}</b> ({e(t['result'] or t['status'])}): {e(t['why'])}</li>" for t in lessons)
        out += "</ul>"
    return out


def render(offers, low, unknown_sv, top, picks, tests, done, groups, cfg, source, demo):
    banner = ('<p style="background:#fef3c7;padding:8px 12px;border-radius:6px;font-size:13px">'
              "Sample data: invented brands and numbers, for showing how the report works.</p>") if demo else ""
    low_rows = [[e(o["brand"]), nv(o["geo"]), f"{o['sv']:,.0f}", e(o["keyword"]) or nv(NV)] for o in low]
    ready = sum(1 for o in offers if o["status"] == "READY TO TEST")
    return f"""<!doctype html><html><head><meta charset="utf-8"><title>Bulls Offer Selection {cfg.today}</title></head>
<body style="font-family:-apple-system,Segoe UI,Roboto,Arial,sans-serif;color:#111827;max-width:1200px;margin:0 auto;padding:24px">
{banner}
<h1 style="font-size:22px;margin:0">Bulls offer selection</h1>
<p style="color:#6b7280;margin:4px 0 0">{cfg.today:%d %b %Y} · input: {e(os.path.basename(source))} ·
{len(offers) + len(low) + len(unknown_sv)} brand/GEO combinations · {len(offers)} pass the {cfg.min_volume:,} search filter ·
{ready} ready to test · {len(picks)} recommended</p>
<p style="font-size:12px;color:#6b7280;margin:8px 0 0">Facts come from the offer list. The conversion rates (0.5%, 1%, 2%, 3%)
are scenarios, not predictions. Nothing here launches a campaign.</p>

{h2(1, "Qualified offers", f"Monthly searches ≥ {cfg.min_volume:,}. One row per brand and GEO, using the best real source. "
    "Real payout = what reaches us after any network share.")}
{qualified_table(offers)}
<h3 style="font-size:14px;margin:22px 0 6px">Economics per click</h3>
<p style="font-size:12px;color:#6b7280;margin:0 0 6px">Revenue per click = real payout × CR. Margin per click = revenue per click − CPC.
Break-even CR = CPC ÷ real payout: the conversion rate needed just to get our money back.</p>
{economics_table(offers)}
<h3 style="font-size:14px;margin:22px 0 6px">Low priority / do not test yet (under {cfg.min_volume:,} searches)</h3>
{grid(["Brand", "GEO", "Search volume", "Keyword"], low_rows)}

{h2(2, "Missing information", "Must be checked before testing. Nothing here was guessed.")}
{missing_section(offers, unknown_sv)}

{h2(3, "Top candidates", "Ranked by score (0–100): search volume 20, payout/economics 25, CPC 20, intent 20, "
    "traffic permissions 10, tracking 5. Missing data scores 0 for that part.")}
{top_section(top)}

{h2(4, "Recommended tests", "Only READY TO TEST offers. Budget = enough clicks to expect 3 conversions at break-even "
    f"(about 3 × the payout), capped at {cfg.max_budget:,.0f} in the offer's currency. If an offer truly converts at break-even, there is only "
    "a ~5% chance of 0 conversions after that many clicks.")}
{test_cards(picks, cfg)}
{tests_section(tests, done, groups, cfg)}
</body></html>"""


def write_csv(path, offers):
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Brand", "Category", "Network", "Account", "GEO", "Keyword", "Search Volume", "Real Payout",
                    "Payout Currency", "Payout Type", "Gross Payout", "Network Share %", "CPC", "CPC Currency",
                    "CPC Source", "CPC Date", "Commercial Intent", "Paid Search Allowed", "Brand Bidding Allowed",
                    "Direct Linking Allowed", "Break-even CR %", "Margin @0.5%", "Margin @1%", "Margin @2%",
                    "Margin @3%", "Priority Score", "Confidence", "Status", "Missing", "Review", "Notes"])
        for o in offers:
            b = o["best"]

            def r(v, d=2):
                return "" if v is None else f"{v:.{d}f}"
            w.writerow([o["brand"], o["category"], b["network"], b["account"], o["geo"], o["keyword"],
                        r(o["sv"], 0), r(b["real"]) or (AOV_REQ if b["payout_issue"] == AOV_REQ else NV), b["currency"],
                        b["payout_type"], b["payout_raw"], r(b["share_pct"], 1) or NV, r(o["cpc_value"]) or CPC_NA,
                        o["cpc_cur"], o["cpc_source"], o["cpc_date"], o["intent"], b["paid_search"],
                        b["brand_bidding"], b["direct_linking"], r(o["be"] * 100 if o["be"] is not None else None),
                        *[r(o["margin"].get(c), 3) for c in CR_SCENARIOS], o["score"], o["confidence"], o["status"],
                        "; ".join(o["missing"]), "; ".join(o["review"] + o["block"]), "; ".join(o["notes"])])


def write_new_tests(path, picks, cfg):
    """Pre-filled test-log rows for the recommended tests. Copy a row into tests.csv only when you launch it."""
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(TEST_COLUMNS)
        for o, p in picks:
            b = o["best"]
            w.writerow(["", o["brand"], o["category"], o["geo"], "", "Google Ads", "", b["network"], b["account"],
                        f"{b['real']:.2f}", b["currency"], f"{o['cpc_value']:.2f}", f"{p['budget']:.2f}", p["clicks"],
                        f"{o['sv']:.0f}", o["intent"], "", "", "", "", "", "", "", "TESTING", "", ""])


TEST_COLUMNS = ["test_id", "brand", "category", "geo", "launch_date", "traffic_source", "ad_account", "offer_source",
                "network_account", "payout", "payout_currency", "planned_cpc", "test_budget", "max_clicks",
                "search_volume", "commercial_intent", "clicks", "spend", "conversions", "revenue", "tracking_working",
                "offer_still_active", "terms_changed", "status", "result", "why"]


# --------------------------------------------------------------------------- main

def main(argv):
    ap = argparse.ArgumentParser(description="Bulls offer selection report.")
    ap.add_argument("offers", nargs="?", help="offer list CSV (see offers_template.csv)")
    ap.add_argument("--tests", help="Bulls test log CSV (see tests_template.csv)")
    ap.add_argument("--demo", action="store_true", help="use the sample files")
    ap.add_argument("--min-volume", type=float, default=200_000, help="monthly searches needed (default 200000)")
    ap.add_argument("--max-budget", type=float, default=300, help="cap on one test's budget (default 300)")
    ap.add_argument("--min-score", type=int, default=50, help="lowest score to recommend a test (default 50)")
    ap.add_argument("--max-tests", type=int, default=5, help="how many tests to recommend at most (default 5)")
    ap.add_argument("--cpc-tolerance", type=float, default=1.25, help="pause if CPC > plan x this (default 1.25)")
    ap.add_argument("--scale-roas", type=float, default=1.3, help="ROAS needed to scale (default 1.3 = 130%%)")
    ap.add_argument("--scale-conversions", type=int, default=3, help="conversions needed to scale (default 3)")
    ap.add_argument("--signal-conversions", type=float, default=3, help="conversions at break-even a test budget buys")
    ap.add_argument("--max-cpc-age", type=int, default=30, help="days before a CPC counts as stale (default 30)")
    ap.add_argument("--today", type=dt.date.fromisoformat, default=dt.date.today())
    cfg = ap.parse_args(argv)
    if cfg.demo:
        cfg.offers = cfg.offers or os.path.join(HERE, "sample_offers.csv")
        cfg.tests = cfg.tests or os.path.join(HERE, "sample_tests.csv")
    if not cfg.offers:
        ap.error("give an offer list CSV, or --demo")

    tests = load_tests(cfg.tests, cfg) if cfg.tests else []
    history = defaultdict(list)
    for t in tests:
        history[(t["brand"].lower(), t["geo"].upper())].append(t)
        history[(t["brand"].lower(), "")].append(t)

    groups = defaultdict(list)
    for row in read_csv(cfg.offers):
        if clean(row.get("brand")):
            groups[(clean(row["brand"]).lower(), clean(row.get("geo")).upper())].append(row)
    all_offers = [evaluate(k, rows, cfg, history) for k, rows in groups.items()]

    rank = lambda o: (STATUS_ORDER[o["status"]], -o["score"])
    offers = sorted([o for o in all_offers if o["qualified"]], key=rank)
    low = sorted([o for o in all_offers if o["qualified"] is False], key=lambda o: -o["sv"])
    unknown_sv = [o for o in all_offers if o["qualified"] is None]
    top = sorted([o for o in offers if o["status"] != "DO NOT TEST"], key=lambda o: -o["score"])[:10]
    picks = [(o, test_plan(o, cfg)) for o in top
             if o["status"] == "READY TO TEST" and o["score"] >= cfg.min_score][:cfg.max_tests]
    done, lessons = learnings(tests)

    os.makedirs(OUT_DIR, exist_ok=True)
    tag = f"{cfg.today.isoformat()}{'_demo' if cfg.demo else ''}"
    report = os.path.join(OUT_DIR, f"bulls_selection_{tag}.html")
    with open(report, "w") as f:
        f.write(render(offers, low, unknown_sv, top, picks, tests, done, lessons, cfg, cfg.offers, cfg.demo))
    write_csv(os.path.join(OUT_DIR, f"bulls_scored_{tag}.csv"), offers + unknown_sv + low)
    write_new_tests(os.path.join(OUT_DIR, f"bulls_new_tests_{tag}.csv"), picks, cfg)
    print(report)
    for o in offers:
        print(f"  {o['status']:<14} {o['score']:>3}  {o['confidence']:<6} {o['brand']} ({o['geo']})")


if __name__ == "__main__":
    main(sys.argv[1:])
