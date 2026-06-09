# AOFM — `playground/econ/aofm/`

Last updated: 2026-06-10

**Status: DB-LIVE** — 157 indicators / 268,195 obs in `econ.fact_indicator`. All 31 XLSX files at `playground/econ/aofm/discovery/xlsx/`. Manual monthly refresh via Edge (see below). Phase G blocker lifted.

> **Previous blocker resolved 2026-06-10:** Corp TLS-inspection on `*.gov.au` resets HTTP/2
> connections for `/sites/default/files/*.xlsx` when using Chrome (BoringSSL TLS stack). Microsoft
> Edge uses the OS Schannel TLS stack and is not affected — direct XLSX downloads succeed in Edge.
> Playwright/Chrome automation remains blocked. The workaround is manual download via Edge
> (`File > Save As` from the data-hub accordions) into `playground/econ/aofm/discovery/xlsx/`.

The Australian Office of Financial Management publishes the only authoritative breakdown of
Australian Government Securities (AGS) **holdings by investor category** — resident vs
non-resident, banks vs non-bank, RBA, etc. ABS BoP gives the *flow* of portfolio investment but
not the stock decomposition by investor type.

## Manual refresh process

1. Open `https://www.aofm.gov.au/data-hub` in **Microsoft Edge**.
2. Expand each accordion section and locate the XLSX download links.
3. Use `File > Save As` to download the relevant files.
4. Drop them into `playground/econ/aofm/discovery/xlsx/` (overwrite in place — filenames are stable).
5. Re-run the relevant fetcher(s): `python playground/econ/aofm/fetch_foreign_holdings.py` etc.
6. Load via the canonical loader: `python -m scripts.migrations.load_econ_indicator_from_playground --vendor aofm`.

AOFM updates most files monthly. `foreign_holdings.xlsx` typically lags ~4 weeks after quarter-end.

## URL generation pattern

XLSX URLs follow:

```
https://www.aofm.gov.au/sites/default/files/{YYYY-MM-DD}/{basename}.xlsx
```

where `{YYYY-MM-DD}` is AOFM's internal publication date — it **rolls forward** every time AOFM
republishes a file. `discover.py` parses the data-hub HTML for current URLs and writes them to
`discovery/{utc_ts}/download_urls.json` (HTML page itself loads fine even in Chrome). Re-run
discovery before each refresh cycle to pick up date-rolled URLs.

## Playground files

| File | Purpose |
|---|---|
| `REFRESH.md` | Monthly manual-refresh runbook (Edge download + load steps). |
| `discover.py` | Playwright probe that walks the data-hub page tree and writes `discovery/xlsx_inventory.json` (31-URL canonical inventory). HTML page loads fine; XLSX links blocked. |
| `explore_aofm.py` | Headed-Chrome REPL (mirrors `explore_jpm.py`). Fresh profile every run; captures any download triggered by user clicks. |
| `connect_aofm.py` | CDP attach helper (`connect_over_cdp`) — attempted workaround for the corp TLS-inspection block. Kept for reference; superseded by the manual-Edge path. |
| `test_edge.py` | Minimal Playwright + `channel="msedge"` smoke that confirmed Edge slips past the corp firewall. |
| `setup_debug_chrome.ps1` | PowerShell helper that launched Chrome with a remote-debugging port for the `connect_aofm.py` attach attempts. |
| `fetch_xlsx.py` | Accordion-aware downloader (`expand section → click XLSX → page.expect_download`). Code path sound; blocked by corp firewall in Chrome. |
| `_aofm_common.py` | Shared helpers (date parsing, wide-to-long reshape, indicator naming). |
| `fetch_foreign_holdings.py` | 34 indicators, quarterly since 2003. Non-resident AGS holdings by investor category (banks, non-banks, RBA, other residents). |
| `fetch_portfolio_aggregate.py` | 16 indicators, monthly since 2003. AGS outstanding by instrument (TB, TIB, TN). |
| `fetch_term_premium.py` | 30 indicators, daily since 1992. AOFM term-premium decomposition: forward yield (FY), term premium (TP), risk-neutral yield (RNY) × 1Y..10Y. |
| `fetch_turnover.py` | 67 indicators. TB + TIB secondary market turnover by region, counterparty, tenor, and category (new vs legacy). |
| `fetch_issuance_buybacks.py` | 10 indicators. Monthly-aggregated TB + TIB + TN gross issuance and buyback flows. |
| `profile/`, `profile_edge/` | Playwright persistent profiles used during the gating debug (kept for reproducing the firewall behaviour). |
| `discovery/inspect_xlsx.py` | One-off scanner — prints sheet-name + column-name signatures for each XLSX (used to scope the 5 parsers vs the 26 skipped files). |
| `discovery/xlsx_inventory.json` | Canonical 31-XLSX URL inventory (filename + current URL + anchor text). Re-run `discover.py` after each AOFM publication cycle. |
| `discovery/xlsx_schemas.txt` | Schema fingerprint output from `inspect_xlsx.py`. |
| `discovery/xlsx/` | Manually-downloaded XLSX files (the `econ.fact_indicator` source of truth for AOFM). |

## Per-fetcher cell mapping

| Fetcher | Indicators | Cell | Key headline |
|---|:---:|---|---|
| `fetch_foreign_holdings.py` | 34 | 3.3 Capital Account | Mar-2026: non-resident holdings AUD 469bn = 50.9% of AUD 922bn outstanding |
| `fetch_portfolio_aggregate.py` | 16 | 1.2 Fiscal Demand | TB + TIB + TN outstanding; monthly stock series |
| `fetch_term_premium.py` | 30 | 4.3 Fin Conditions | 10Y term premium Mar-2026: 95bp |
| `fetch_turnover.py` | 67 | 4.3 Fin Conditions | Secondary market liquidity by instrument / counterparty |
| `fetch_issuance_buybacks.py` | 10 | 1.2 Fiscal Demand | Monthly gross issuance and buyback flows |

## Skipped files (out of scope for econ schema)

The following XLSX files were reviewed and explicitly excluded. They would require a separate
`dbo.dim_bond_instrument + rates.fact_bond_outstanding` schema or are near-duplicates/one-offs:

- Per-bond-line detail workbooks (`portfolio_aggregate_-_treasury_bonds_-_settlement.xlsx` and
  siblings with 80-254 columns per bond line).
- `portfolio_aggregate_-_settlement.xlsx` — near-duplicate of `_dealt_4`.
- `portfolio_aggregate_-_executive_summary_-_dealt.xlsx` — covered by `_dealt_4`.
- IR swaps (AUD + cross-currency) — AOFM internal hedging, not macro indicators.
- RMBS (one-off 2008-2018 GFC purchases).
- Securities lending facility.
- Retail register buybacks.
- Treasury indexed bonds indexation factors.
- TB/TIB syndications and conversions (per-tender detail; aggregated in issuance/buybacks).

## DB state (as of 2026-06-10)

- AOFM: 157 indicators / 268,195 obs (`dim_vendor.vendor_code = 'aofm'`, id=29, vendor_type='web')
- Migration 088 applied: `dbo.dim_vendor` row inserted.
- **AU total: 379 indicators / 339,631 obs** (ABS 141 + RBA 78 + AOFM 157 + FRED-mirror 3).

## Historical blocker context (2026-06-09)

Chrome and Playwright automation were blocked by corp TLS-inspection resetting HTTP/2 on
`*.gov.au/sites/default/files/*.xlsx`. The data-hub HTML page loaded fine; only the XLSX download
path was reset. Plain `httpx` / `curl` timed out at TLS handshake (exit 56). After a few failed
XLSX attempts the firewall also blocked the HTML page temporarily. Edge (Schannel) was the solution.

## Related

- [`../australia_indicator_inventory.md`](../australia_indicator_inventory.md) — 4×4 tracker, AOFM fetcher table, full score.
- [`../index.md`](../index.md) — AOFM access-path row (now DB-LIVE).
- [`../../macro_economy_wiring_map.md#77-australia-au`](../../macro_economy_wiring_map.md#77-australia-au) — §7.7 cells updated for AOFM contributions.
- [Indonesia DJPPR](../../indonesia/_playground/bps.md) — analogous Indonesian bond-ownership-by-investor source.
