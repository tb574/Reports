# Affise CPS daily revenue report

Builds a daily report of CPS revenue for management from the Affise Admin API
(`api-nyjltb.affise.com`).

## What it shows
- Yesterday vs 2 days ago, side by side: income, payout, profit, margin, conversions (approved and pending), clicks, CR and EPC, with the % change
- Both days broken down by publisher and by offer. The publisher table shows how many campaigns each publisher ran: offers with at least 50 clicks from that publisher on that date (`MIN_CAMPAIGN_CLICKS`), from Affise stats split by date, offer and publisher and checked against the publisher totals
- Income by network (digidip, Impact, FlexOffers, ...): yesterday, 2 days ago, month to date and last month, for networks that made money yesterday or 2 days ago (the total still covers all networks). The network comes from the prefix of each offer's Affise external offer ID (`dd_`, `imp_ny_`, `fx_`, ...); the mapping is `NETWORKS` in `daily_report.py`
- Last month (the full previous calendar month): totals, a breakdown by publisher (with campaigns run that month) and the top 10 offers by income
- Offer tables list only offers with conversions (in the two-day table, on either day); totals still include every offer
- Month to date up to yesterday: income, profit, a run-rate forecast and a daily income trend

Today is never included, because its numbers are still incomplete.

All amounts are in USD: Affise converts sales in other currencies (e.g. EUR offers) into the account currency. Income is what the networks pay us (the Affise field `charge`). Payout is the publisher's share (the Affise field `revenue`). Profit is income minus payout.

## Run
```bash
export AFFISE_API_KEY=...            # Affise → Settings → Security
python3 daily_report.py              # report for yesterday
python3 daily_report.py 2026-09-27   # report for a specific day
python3 daily_report.py --demo       # sample data, no API call
```
Each run writes to `output/`:
- `cps_revenue_<date>.html`, the report to email
- `daily_log.csv`, one row per day, which feeds the Drive log sheet
- `raw_<date>.json`, the raw numbers

## Drive log
Google Sheet: "Affise CPS Daily Revenue Log"
https://docs.google.com/spreadsheets/d/1yjxHAwj67rh7drNGWTEy-0CePcgt6Bpi3sKXbpHJ6qI/edit

## Settings
| Env var | Default |
|---|---|
| `AFFISE_API_URL` | `https://api-nyjltb.affise.com` |
| `REPORT_CURRENCY` | `USD` |
| `REPORT_OUT_DIR` | `./output` |
