# Treasury Fiscal Data — `playground/econ/us/treasury/`

**Status:** Discovery built (playground). Dry-run clean; fiscal identity (receipts − outlays = deficit/surplus) verified diff=0. Vendor row (`TREASURY`) pending migration 105 — not yet loaded into `econ.fact_indicator`. No `scripts/econ/us/` entry. Not wired into any orchestrator.

Note on vendor code: `vendor_name="TREASURY"` in the fetchers. On promotion into `dbo.dim_vendor`, the row will be registered as `treasury_us` to disambiguate from any future `treasury_au` entry.

Treasury Fiscal Data API. **Keyless** REST JSON at `https://api.fiscaldata.treasury.gov/services/api/fiscal_service/{path}`. The connector auto-paginates via `meta.total-pages`.

## Contents

| File | Purpose |
|---|---|
| `connector.py` | `TreasuryClient` — keyless GET client with `get_all()` auto-pagination. Follows `meta.total-pages`; respects `page[size]` (default 10,000). |
| `fetch_mts.py` | 3 Monthly Treasury Statement series — federal receipts, outlays, surplus/deficit. Cell 1.2. |
| `fetch_debt.py` | 1 Debt to the Penny series — total public debt outstanding, daily. Cells 1.2 / 4.2. |

## Series breakdown

### `fetch_mts` — 3 series (endpoint `v1/accounting/mts/mts_table_1`, unit `usd_mn`, monthly, NSA, category `other`)

| IMDR code | Description | Sign convention |
|---|---|---|
| TREASURY.FISCAL.RECEIPTS.US | US Federal Government Monthly Receipts | positive |
| TREASURY.FISCAL.OUTLAYS.US | US Federal Government Monthly Outlays | positive |
| TREASURY.FISCAL.DEFICIT.US | Monthly Surplus/Deficit | + = surplus, − = deficit |

The MTS table publishes a snapshot of **all months in the current fiscal year** at each `record_date` (month-end). The fetcher filters to `record_type_cd=MTH` rows (individual months, not YTD). When the same calendar month appears across multiple publications (revisions), the most recent `record_date` wins. Prior-fiscal-year block rows (`src_line_nbr < 15`) are skipped to avoid double-counting.

FY-start logic: US fiscal year runs October–September. `obs_date` is derived from `classification_desc` (month name) + FY-start year inferred from the publication date. October/November/December map to `fy_start_year`; January–September map to `fy_start_year + 1`.

Raw `current_month_dfct_sur_amt` is sign-positive-for-deficit; the fetcher negates before storing so that positive = surplus.

### `fetch_debt` — 1 series (endpoint `v2/accounting/od/debt_to_penny`, unit `usd_mn`, daily, NSA, category `balance_sheet`)

| IMDR code | Description |
|---|---|
| TREASURY.DEBT.TOTAL_PUBLIC.US | US Total Public Debt Outstanding (Debt to the Penny) |

Raw field `tot_pub_debt_out_amt` is in actual USD; the fetcher divides by `1e6` to store as `usd_mn`. From 2015-01-01 that is approximately 2,800 rows (weekdays Treasury publishes). Sanity range: ~$36–40 trillion → ~36,000,000–40,000,000 in `usd_mn`.

## Gotchas

- **No API key required.** The Treasury Fiscal Data API is fully open. `TreasuryClient` sends no auth header. Do not confuse this API with the TreasuryDirect or TIC APIs, which have different auth models.
- **Treasury TIC foreign holdings is NOT in this API.** The TIC dataset (foreign holdings of US securities) is published as CSV/XML at `home.treasury.gov/data/treasury-international-capital-tic-system`. It is not accessible via `api.fiscaldata.treasury.gov`. Cell 3.3 TIC stock is a deferred scrape; the BEA ITA financial account covers the flow side.
- **MTS `record_type_cd` filter is essential.** Without filtering to `MTH` rows, the API also returns YTD, fiscal-year-total, and header rows which have different value semantics.
- **MTS FY-start logic.** The `_obs_date_from_row()` function in `fetch_mts.py` documents the src_line_nbr-based prior-FY/current-FY block split in detail — read it before modifying the date derivation.

## Canonical loader

```bash
python -m playground.econ.us.treasury.fetch_mts
python -m playground.econ.us.treasury.fetch_debt
# After vendor registration (migration 105):
python -m scripts.migrations.load_econ_indicator_from_playground --vendor treasury_us
```

## Related

- [us_coverage_plan.md](../us_coverage_plan.md) — cells + build order
- [united_states_indicator_inventory.md](../united_states_indicator_inventory.md) — playground fetcher inventory
