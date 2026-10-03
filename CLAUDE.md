# Notes for Claude

## Bulls offer selection (`bulls/`)
When the user sends a list of affiliate offers for Bulls (campaigns paid with our own ad budget), follow
`bulls/README.md`: put the list into the `offers_template.csv` columns, run
`python3 bulls/select_offers.py <offers.csv> --tests <test log>` and answer with four sections:
1. Qualified offers  2. Missing information  3. Top candidates  4. Recommended tests (3–5, with budget and stop rules).

Rules: never invent data (empty = NOT VERIFIED, CPC NOT AVAILABLE, AOV REQUIRED); never assume paid search, brand
bidding or direct linking are allowed; always use the real payout after network share; never mark READY TO TEST when
tracking or traffic permissions are unclear; separate facts from assumptions; keep every test in the test log;
never launch or change a campaign. The user is not a developer: keep explanations short and practical.
