# APRA MADIS — `scripts/econ/au/apra/` (library: `src/imdr/domains/econ/apra_madis.py`)

Last updated: 2026-07-14

**Status:** DB-LIVE — 1 fetcher, **8 indicators / 696 obs** loaded (DB-verified 2026-07-14). `apra` vendor row pre-existed (migration 092, for the Track-B quarterly ADI performance filings) — this fetcher reuses it. Wired into `au_monthly`.

Note: this is a distinct dataset from the pre-existing `scripts/econ/au/govt/fetch_apra_quarterly.py` (Track B — quarterly ADI/GI performance *documents* into `research.dim_report`). MADIS is Track A — monthly *time-series* into `econ.fact_indicator`.

Why we care: RBA D2 gives system-wide housing credit aggregates (owner-occ / investor, NSA+SA). APRA's Monthly ADI Statistics (MADIS) is the only free source that splits housing credit **by individual bank** — useful for tracking big-4 market-share shifts in owner-occupier vs investor lending.

## Source

`https://www.apra.gov.au/monthly-authorised-deposit-taking-institution-statistics` — APRA publishes two files off this page each month:

- the current-month workbook (wide "Table 2" layout, one sheet per month) — **not used**.
- the **back-series** workbook: a single long-format sheet ("Table 1") with one row per `(Period, ABN, Institution Name)`, covering the full history. Verified 2026-07-14: 87 monthly periods (2019-03-31 → 2026-05-31), 10,886 rows, 195 ADIs. Already carries the latest month, so this is the sole file needed.

The page also still hosts a legacy pre-MADIS-rename file ("Monthly banking statistics June 2019 back series") under a different anchor-text prefix — excluded by the discovery regex's text match (`discover_backseries_url` requires the anchor text to start with "monthly authorised deposit-taking institution statistics" AND contain "back-series"/"back series").

Confirmed public / plain HTTP GET, no auth, no browser needed (curl 200 OK verified 2026-07-14) — same reachability as the quarterly ADI performance filings; not subject to the AOFM corp-firewall block.

## Series

Columns extracted from Table 1: `Loans to households: Housing: Owner-occupied` and `Loans to households: Housing: Investment` (both AUD million), filtered to the big-4 by institution legal name:

| Institution (as it appears in the file) | Bank code |
|---|---|
| Australia and New Zealand Banking Group Limited | ANZ |
| Commonwealth Bank of Australia | CBA |
| National Australia Bank Limited | NAB |
| Westpac Banking Corporation | WBC |

| IMDR code | Series |
|---|---|
| `APRA.ADI.{BANK}.HOUSING_OWNER_OCC.AU` | Owner-occupier housing loans outstanding, AUD million |
| `APRA.ADI.{BANK}.HOUSING_INVESTOR.AU` | Investor housing loans outstanding, AUD million |

4 banks × 2 series = **8 indicators**. Monthly, 2019-03 → present.

**No system-total row** exists in the back-series long format (unlike the current-month wide file's "TOTAL" row in Table 2) — a system aggregate would require summing all ~195 ADIs, out of scope here. Only the big-4 (plus any future `BANK_MAP` additions) are emitted.

## Transport

Plain `httpx` GET for the publication page → regex-match the back-series XLSX anchor → plain `httpx` GET for the XLSX → `openpyxl` (read-only, long-format sheet parse). No Playwright, no corp-firewall issue (unlike AOFM's `*.gov.au/sites/default/files/*.xlsx` path).

## Related

- [`../australia_indicator_inventory.md`](../australia_indicator_inventory.md) — 4×4 tracker cell 4.1
- RBA D2 credit aggregates (`rba.md`) — system-wide housing credit, the aggregate this fetcher splits by bank
- Migration: pre-existing `apra` vendor row from migration 092 (Track B)
