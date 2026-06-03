# Citi Velocity — Exploration Snapshots

Last updated: 2026-06-03

Frozen discovery snapshots from `tagbrowsing` API runs. **Do not re-run** the underlying scripts — all results are cached in `data/cache/{domain}/*.json`.

- **[bonds_full.md](bonds_full.md)** — Sovereign bonds + adjacent fixed income deep probe. 19 RATES.* branches probed, 14 confirmed working: SOV (11.8K, 34 DM countries, full yield+spread+ASW cube), TSY, T_BILL, TIPS, SSA (708, 35 issuers), SSA_CS, MBS (11.3K), AGENCY_INVENTORY, FRA (incl. KRW), FRA_OIS, OIS_INVOICESPREAD, FORECAST. Resolves SOV vs SOV_CMT alias. Supersedes "partial" claims in rates_full.md. Discovered 2026-05-25.
- **[rates_full.md](rates_full.md)** — 135,915 tags across 24 RATES subcategories (SOV_CMT, XCCY_OIS_SWAP, BENCH_RATES, TSY, T_BILL, TIPS, INFLATION, SSA, CITIPAIN, CTOT, etc.). Discovered 2026-03-26. **Note**: SOV/MBS/AGENCY_INVENTORY entries superseded by [bonds_full.md](bonds_full.md).
- **[rates_inflation.md](rates_inflation.md)** — 7,476 inflation tags: CPI indices + inflation swaps + swaptions. Discovered 2026-03-26.
- **[rates_sov_cmt.md](rates_sov_cmt.md)** — SOV_CMT deep dive: 8,250 tags, 32/34 countries confirmed, 30 tenors. Discovered 2026-03-26. **Note**: canonical browsable path is `RATES.SOV.CMT.*`; `RATES.SOV_CMT.*` is a non-enumerable alias. See [bonds_full.md](bonds_full.md).
- **[rates_xccy_ois.md](rates_xccy_ois.md)** — XCCY_OIS_SWAP deep dive: 76,418 tags, all 90 G10 pairs confirmed, spot + forward surface. Discovered 2026-03-26.
- **[rates_basis_swaps.md](rates_basis_swaps.md)** — Tenor basis swaps (3s6s). 4 ccys wired (EUR/AUD active, USD/GBP ceased 2025-02 post-LIBOR). 20-tenor grid. Tag layout `{prefix}.{TENOR}.{QUOTE}` (quote LAST). Discovered 2026-06-03.
- **[rates_ois_meeting.md](rates_ois_meeting.md)** — OIS meeting-date rates exploration.
- **[fx_spot_forward.md](fx_spot_forward.md)** — FX SPOT (52 ccys) + FORWARD (35 bases, 29 tenors, 56 USD quotes) + VOL deep dive (39 base ccys, 11 strikes, 14 tenors). Discovered 2026-04-21.
- **[equity.md](equity.md)** — 9,779 equity tags: VARSWAP, EQIVOL, VOLSWAP, CITI_EQ_INDICES, PRIME, FORECAST. 24 index tickers. Discovered 2026-03-26.
- **[commodities.md](commodities.md)** — 1,202 commodities tags: IMPLIED_VOL (Brent/WTI/XAU/XAG/XPT), FORECAST (6 sectors), EIA (16 weekly petroleum series). Discovered 2026-03-26.
