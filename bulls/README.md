# Bulls offer selection & testing

Bulls campaigns are paid for with our own ad budget. This tool takes a list of affiliate offers and shows which ones
are worth a test, how much to spend and when to stop. **It never launches anything.**

## How to use it (the short version)
1. Fill in `offers_template.csv`: one row per offer **per network** (Google Sheets → File → Download → CSV works).
   Leave a cell empty when you don't know it. Empty means NOT VERIFIED; nothing is guessed.
2. Keep every test in a test log built from `tests_template.csv`.
3. Send both files to Claude (or run the script yourself):
   ```bash
   python3 select_offers.py offers.csv --tests tests.csv
   python3 select_offers.py --demo        # sample data with invented brands
   ```
4. Open `output/bulls_selection_<date>.html`.

## What the report contains
1. **Qualified offers**: brands with ≥ 200,000 monthly searches, one row per brand + GEO, with the best source,
   real payout, CPC, intent, permissions, break-even CR, margin per click at 0.5 / 1 / 2 / 3% CR, score, confidence and status.
   Brands under 200,000 are listed separately as *low priority / do not test yet*.
2. **Missing information**: what must be checked per offer before it can be tested.
3. **Top candidates**: top 10 by score, with the score breakdown and why each source was chosen.
4. **Recommended tests**: at most 5 offers that are READY TO TEST, each with why it is interesting, main risk,
   break-even CR, budget, maximum clicks, stop rules and what would justify scaling.
5. **Test control** (with a test log): every test with spend, revenue, ROAS, CR and a stop-rule check.
6. **Learning from results**: finished tests grouped by category, GEO, network, intent, CPC, payout and search volume.

Also written: `bulls_scored_<date>.csv` (all offers, for a spreadsheet) and `bulls_new_tests_<date>.csv`
(pre-filled test-log rows for the recommended tests; copy a row into your test log only when you actually launch it).

## The rules it follows
- **Real payout** = payout shown × (1 − network share %). The gross payout is never used for the economics.
- **Percentage (CPS) offers**: shown as AOV REQUIRED until a verified average order value is entered.
- **Break-even CR** = CPC ÷ real payout. Above 3% → DO NOT TEST (loses money in every scenario).
- CPC and payout must be in the same currency. Nothing is converted, so no exchange rate is invented.
- A CPC older than 30 days must be re-checked.
- **Best source**: usable sources first (active, approved, paid search and brand bidding allowed), then the highest
  real payout, then tracking reliability and cookie window. A better-paying source that isn't cleared yet is mentioned.

**Status**
| Status | Meaning |
|---|---|
| READY TO TEST | All data present, everything allowed, nothing to review |
| NEEDS REVIEW | Data present, but something needs a human look (pending approval, LOW intent, stale CPC, restrictions, failed before, break-even above 2%…) |
| MISSING DATA | Something critical is NOT VERIFIED |
| DO NOT TEST | Under 200,000 searches, inactive, rejected, paid search or brand bidding not allowed, or break-even above 3% |

**Score (0–100)**: missing data scores 0 for that part.
| Part | Points | How |
|---|---|---|
| Search volume | 20 | 200k: 10 · 500k: 14 · 1M: 17 · 2M+: 20 |
| Payout / economics | 25 | break-even CR ≤0.5%: 25 · ≤1%: 20 · ≤1.5%: 15 · ≤2%: 10 · ≤3%: 5 |
| CPC | 20 | ≤0.30: 20 · ≤0.60: 16 · ≤1: 12 · ≤2: 8 · ≤4: 4 |
| Commercial intent | 20 | HIGH 20 · MEDIUM 10 · LOW 0 |
| Traffic permissions | 10 | paid search 4 · brand bidding 4 · direct linking 2 |
| Tracking / source | 5 | tracking HIGH 3 / MEDIUM 2 · conversions reconcilable 2 |

**Confidence**: HIGH = nothing critical missing · MEDIUM = 1–2 gaps or a stale CPC · LOW = 3+ gaps or no economics.

**Test budget**: enough clicks to expect 3 conversions if the offer only breaks even, i.e. about 3 × the payout,
capped at 300 (change with `--max-budget`). If an offer truly converts at break-even, the chance of 0 conversions after
that many clicks is about 5%, so 0 conversions at the limit is a clear signal.

**Stop rules** for each test: pause and review when spend reaches the budget, clicks reach the limit, 0 conversions at
halfway, actual CPC more than 25% above plan, tracking not working, offer terms change or the offer goes inactive.
A test that ends with 0 conversions is flagged and not relaunched without a new reason.
**Scale** only with at least 3 conversions and ROAS of 130% or more, confirmed by the network.

## Offer list columns (`offers_template.csv`)
| Column | What to enter |
|---|---|
| brand, category | Brand name; category such as VPN, Finance |
| network, network_account | Where the offer is and which of our accounts |
| geo | Country code (US, UK, DE…) |
| payout_type | CPA, CPL, CPI, CPS… |
| payout_value | Fixed amount (`40`) or percentage with a % sign (`8%`) |
| payout_currency | USD, EUR, GBP… |
| network_share_pct | % the network keeps from the payout shown. **0** if the payout shown is already ours |
| offer_status | Active / Paused / … |
| approval_status | Approved / Pending / Rejected / Not applied |
| affiliate_link | Our tracking link |
| paid_search_allowed, brand_bidding_allowed, direct_linking_allowed | Yes / No (empty = NOT VERIFIED) |
| other_restrictions | Anything else from the terms |
| cookie_days | Cookie / referral window in days |
| tracking_reliability | HIGH / MEDIUM / LOW |
| conversions_reconcilable | Yes / No: can we match conversions with the network's report? |
| keyword, search_volume, search_volume_source | The keyword that best shows purchase intent and its monthly Google volume (don't add up unrelated keywords) |
| cpc, cpc_currency, cpc_source, cpc_date | Current CPC, where it came from, date checked (YYYY-MM-DD) |
| commercial_intent, intent_reason | HIGH / MEDIUM / LOW and a short reason |
| verified_aov | Only for % offers: verified average order value or historical revenue per conversion |
| notes | Free text |

Use a dot for decimals (`0.35`). Brand-level fields (keyword, volume, CPC, intent) only need filling on one row per brand.

## Test log columns (`tests_template.csv`)
test_id, brand, category, geo, launch_date, traffic_source, ad_account, offer_source, network_account, payout,
payout_currency, planned_cpc, test_budget, max_clicks, search_volume, commercial_intent, clicks, spend, conversions,
revenue, tracking_working, offer_still_active, terms_changed, status (TESTING / SCALE / PAUSE / STOP / REVIEW),
result (e.g. PROFIT, LOSS, ZERO CONVERSIONS), why (why it worked or failed).

## Settings
| Option | Default |
|---|---|
| `--min-volume` | 200000 |
| `--max-budget` | 300 per test |
| `--min-score` | 50 (lowest score to recommend) |
| `--max-tests` | 5 |
| `--cpc-tolerance` | 1.25 (pause at +25% CPC) |
| `--scale-roas` / `--scale-conversions` | 1.3 / 3 |
| `--max-cpc-age` | 30 days |
