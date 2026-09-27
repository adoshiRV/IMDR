# Quick Monitor — per-country data audits

Companion to the **master spec** [`../quick_monitor.md`](../quick_monitor.md) — the single
authoritative spec (markets + econ/macro layers, reconciled data state, IN/KR completion punch-list).
The per-country files here are the **ticker-by-ticker reference detail** behind it.

**Purpose (the first level):** before building anything, prove — panel by panel, ticker by
ticker — whether IMDR holds the data to **recreate each reference monitor in its entirety**.
Each country doc is a coverage matrix: every Bloomberg series the sheet pulls → the IMDR
source that replaces it → a verdict (✓ have · ◐ partial/derivable · ✗ gap).

The reference workbooks live in `data/quick_monitor/` (manual Bloomberg monitors). The audit
extracts their tickers directly from the workbook formulas/cells, so the inventory is exact,
not guessed.

| Country | Reference workbook | Doc | Status |
|---|---|---|---|
| India | `Market India 1.xlsm` | [`india.md`](india.md) | audited 2026-07-17 (161 tickers); reconciled 2026-07-22 |
| Korea | `MarketMonitor Korea 1.xlsm` | [`korea.md`](korea.md) | audited 2026-07-17; reconciled 2026-07-22 (fiscal + PPI held) |
| China | `MarketMonitor China 1.xlsm` | *pending* | Phase 2+ |
| Australia | `MarketMonitor Australia 1.xlsm` | *pending* | Phase 2+ |

**Verdict key:** ✓ held & fresh in IMDR · ◐ derivable from held data, or held-but-partial
(onshore/offshore nuance, wrong cut, stale) · ✗ genuine gap (needs a pipeline or a source decision).
