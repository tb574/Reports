# Affise CPS daily revenue report

Builds a daily report of CPS revenue for management from the Affise Admin API
(`api-nyjltb.affise.com`).

## What it shows
- Yesterday: income, payout, profit and margin, conversions (approved, pending and declined), clicks, CR and EPC, compared with the day before
- Month to date: income, profit and a run-rate forecast for the month
- Breakdowns by publisher and by offer
- A daily income trend for the month

Income is what the networks pay us (the Affise field `charge`). Payout is the publisher's share (the Affise field `revenue`). Profit is income minus payout.

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
| `REPORT_CURRENCY` | `USD` (display label only; Affise returns totals in the account currency) |
| `REPORT_OUT_DIR` | `./output` |
