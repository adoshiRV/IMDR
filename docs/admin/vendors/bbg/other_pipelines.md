# BBG Feed — Other Pipelines (Credit / Bonds / Futures / Fixings / Listed)

Brief documentation for the non-FX/Rates refreshers. These are domain-specific fetchers invoked by `master.R` but less central to the core FX/Rates ingestion effort. Covered at lower depth — revisit if/when IMDR wants to ingest these.

## Credit

**Script**: [`Credit/bbg_refresh_credit.R`](../../../../../../Business/Research/Dashboard/DataSources/BBG/Credit/bbg_refresh_credit.R).
**Config**: `Credit/Credit.xlsx` with schema `Type | Ccy | Other | Tickers...`.
**Raw cache**: `Credit/_Raw/credit.rda`.
**Output**: `Credit/{Ccy}/{Other}/{Ccy}_{Other}.csv`.
**Lookback**: 1000 days (!) — longest of any domain.

### Series tracked
- `CDS_ASIA_IG` — Asia IG CDS
- `CDS_CHINA`, `CDS_INDO`, `CDS_KOREA`, `CDS_MALAY`
- `CDS_EUROPE`
- `CDX5y` — North America CDX 5Y
- Various CDS single-name / index tenors

### Special-case
```r
if (tickers == "CDX HY CDSI GEN 5Y SPRD Corp") {  # pad missing today's row
    if (currDate not in temp_data$date) {
        # duplicate the latest known value for today
        temp_data = rbind(temp_data, new_data)
    }
}
```
Handles a known gap in BBG's publication of this one index — forces the current date to be present using the previous value.

## Bonds

**Script**: [`BONDS/bbg_refresh_bonds.R`](../../../../../../Business/Research/Dashboard/DataSources/BBG/BONDS/bbg_refresh_bonds.R).
**Config**: `BONDS/Bonds data file.xlsx` with schema `Type | Ccy | Other | Tickers...`.
**Raw cache**: `BONDS/_Raw/bond.rda`.
**Output**: `BONDS/{CCY}/...`.
**Fields**: `px_last` + `yld_ytm_mid` (unique to bonds — other domains fetch only `px_last`).

### Currency coverage
`AUD`, `CNY`, `IDR`, `INR`, `JPY`, `KRW`, `MYR`, `SGD`, `THB`, `USD`.

### Linker-specific handling
```r
if (iden == "USD_LINKER") {
    # special path for US inflation-linked securities
}
```
USD inflation-linked bonds have their own handling — the details are deeper in the script.

## Futures

Four scripts invoked serially from `master.R`:
- [`FUTURES/bbg_refresh_futures.R`](../../../../../../Business/Research/Dashboard/DataSources/BBG/FUTURES/bbg_refresh_futures.R) — main futures
- [`FUTURES/CTD futs daily update.R`](../../../../../../Business/Research/Dashboard/DataSources/BBG/FUTURES/CTD%20futs%20daily%20update.R) — cheapest-to-deliver
- [`FUTURES/ED_FF_IR_KE_KAA_SFR_Xm_YM daily update.R`](../../../../../../Business/Research/Dashboard/DataSources/BBG/FUTURES/ED_FF_IR_KE_KAA_SFR_Xm_YM%20daily%20update.R) — front-month codes for specific contracts
- [`FUTURES/rolled futs daily update.R`](../../../../../../Business/Research/Dashboard/DataSources/BBG/FUTURES/rolled%20futs%20daily%20update.R) — roll-adjusted continuous series

### Configs
- `Futures Data File.xlsx` — main
- `CTD futs.xlsx`
- `ED_FF_IR_KE_KAA_SFR_Xm_YM file.xlsx`
- `rolled futs.xlsx`
- `spot_Xm_YM file.xlsx`
- `BBG futures roll adjustments.xls`
- `XCTK.xlsm` — crude extras

### Contract codes (folder names in `FUTURES/`)
~40 codes: BC, CL, CO, ED, ER, ES, FF, FV, GC, HC, HG, HI, HJA, HU, IH, INB, INO, INT, IR, JB, KAA, KE, KM, NK, NQ, PA, PL, QZ, RX, SFR, SI, TU, TY, UB, US, UX, UXY, WN, XCTK, XM, XU, XUC, YM

Each folder holds per-contract CSVs. Rolled series live under a separate naming convention managed by `rolled_futs_creator.R`.

## Fixings (IR)

**Script**: [`FIXINGS/IrFixings.R`](../../../../../../Business/Research/Dashboard/DataSources/BBG/FIXINGS/IrFixings.R).
**Config**: **Hardcoded** inside the R script — `bbgIndexMap` named vector (approximately 40 mappings).

Pattern:
```r
bbgIndexMap = c(
    'CPURNSA Index'     = 'USD-CPURNSA',
    'TTHORON Index'     = 'THB-THOR-ON',
    'SOFRRATE Index'    = 'USD-SOFR-ON',
    'FEDL01 Index'      = 'USD-FEDFUNDS-ON',
    'US0003M Index'     = 'USD-LIBOR-3M',
    ... (~40 entries)
)
```

**Coverage highlights**:
- USD inflation: `CPURNSA`
- Central bank overnight rates: THB-THOR, CAD-CORRA, CHF-SARON, NOK-NOWA, PLN-NBP, SEK-STIBOR-ON, GBP-SONIA, EUR-ESTR, USD-SOFR, USD-FEDFUNDS, INR-MIBOR-ON, SGD-SOR-ON, NZD-NZOCRS, AUD-AONIA, JPY-TONAR, ILS-SHIR
- IBOR fixings: USD-LIBOR-3M/6M, GBP-LIBOR-3M/6M, JPY-LIBOR-3M/6M, JPY-DTIBOR-3M/6M, CHF-LIBOR-6M, NOK-NIBOR-3M/6M, PLN-WIBOR-3M/6M, EUR-EURIBOR-3M/6M, CAD-CDOR-3M, NZD-BKBM-3M, AUD-BBSW-1M/3M/6M, SGD-SOR-3M/6M, HKD-HIBOR-1M/3M, CNY-SHIBOR-3M, CNY-REPO-7D, KRW-91D_CD-3M, MYR-KLIBOR-3M, THB-THBFIX-6M, TWD-TAIBOR-3M

**Decommissioned**:
- `EONIA Index` → `EUR-EONIA-ON` (retired 2021-12-31)
- `WIBR3M/6M Index` → `PLN-WIBOR-3M/6M` (BBG stopped publishing 2022-04-19)

**Output**: `FIXINGS/_Out/{series}.csv` or similar — detail not captured in this pass.

There's also an `FxFixings.R` sibling script — FX fixings (WMR etc.).

## Listed

**Script**: [`Listed/listed.R`](../../../../../../Business/Research/Dashboard/DataSources/BBG/Listed/listed.R) → [`Listed/listedFct.R`](../../../../../../Business/Research/Dashboard/DataSources/BBG/Listed/listedFct.R).
**Input**: `Listed/Input/...` (copied in by `CopyListedInput.R`).
**Output**: `Listed/bond_MKT=YYYY-MM-DD_MKTCUTOFF={cutoff}.csv` — snapshot per date + cutoff.

Example output files seen:
- `bond_MKT=2022-05-03_MKTCUTOFF=USA.csv`
- `bond_MKT=2022-05-04_MKTCUTOFF=LIVE.csv`
- `bond_MKT=2022-05-10_MKTCUTOFF=USA.csv`
- `bond_MKT=2022-05-10_MKTCUTOFF=LIVE.csv`
- `Bond_MKT_with_tax=2025-07-08_MKTCUTOFF=LIVE.csv`

So `MKTCUTOFF` is one of `LIVE`, `USA`, `ASIA` (matching our FX probe's cutoff semantics). This is bond-position + benchmark pricing for tax-adjusted P&L, tied into a separate Excel macro workflow.

Not a primary target for IMDR.

## FX-OIS

Tiny folder: just 4 ccy subfolders (AUD, GBP, NZD, USD) and a shortcut file. Unclear what populates it — possibly output from `FUTURES/CTD futs daily update.R` or a manual dashboard.

**Not covered further.**

## FX_30mins, FX_BFIX

Separate intraday FX trees:
- `FX_30mins/` — 30-minute snapshots (script not yet located).
- `FX_BFIX/` — Bloomberg FX Fixing (BFIX) specifically.

Not invoked from `master.R` — probably separate scheduled jobs.

## Priority assessment for IMDR

| Domain | Priority | Reason |
|---|---|---|
| FX | **P0** | Daily outrights are immediately useful — dual-source with Citi |
| Rates (IRS/OIS) | **P0** | EM coverage (MYR, KLIBOR, KRW-91D_CD, TAIBOR, SHIBOR) beyond Citi |
| BASIS | **P1** | Cross-ccy basis for funding analysis |
| Fixings | **P1** | IR fixings not in IMDR yet |
| Credit | **P2** | CDS — specific research use case |
| Bonds | **P3** | Large data; separate design needed |
| Futures | **P3** | Futures have their own ingestion story |
| Vol | **P3** | Citi already covers core 17 pairs |
| Listed | **P4** | Position-level, not market data |
| FX-OIS | **P4** | Small / unclear |
| FX_30mins / FX_BFIX | **P4** | Intraday — separate design |

See [imdr_integration_plan.md](imdr_integration_plan.md) for the roadmap.
