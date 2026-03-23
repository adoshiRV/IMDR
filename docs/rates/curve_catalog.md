# Rates Curve Catalog

Complete inventory of all interest rate curves tracked in IMDR, their lifecycle status, data availability, and quote type coverage.

Source of truth: `src/imdr/universe/rates.yml` → `rates.dim_curve` table.

---

## Curve Lifecycle Statuses

| Status | Meaning |
|--------|---------|
| **active** | Currently publishing. Pulled daily by live pipeline. |
| **reformed** | Methodology changed but still publishing (e.g. EURIBOR hybrid, MIFOR→SOFR-based). |
| **ceased** | No longer publishing after cessation date. Historical data only. |

---

## OIS Curves (Risk-Free Rates)

16 curves across G10 + Asia. All use `RATES.OIS.{CCY}_{INDEX}.{QUOTE}.{TENOR}` tag format.

| # | CCY | Curve | Status | Primary From | Supersedes | Cessation | Notes |
|---|-----|-------|--------|-------------|------------|-----------|-------|
| 1 | AUD | AONIA | active | — | — | — | |
| 2 | CAD | CORRA | active | 2024-06-28 | CDOR | — | |
| 3 | CHF | SARON | active | 2022-01-01 | CHF_LIBOR | — | |
| 4 | EUR | EONIA | **ceased** | — | — | **2022-01-03** | Superseded by EUROSTR |
| 5 | EUR | EUROSTR | active | 2022-01-03 | EONIA | — | |
| 6 | GBP | SONIA | active | 2022-01-01 | GBP_LIBOR | — | |
| 7 | JPY | TONAR | active | 2022-01-01 | JPY_LIBOR | — | |
| 8 | JPY | TONAR_JSCC | active | — | — | — | JSCC-cleared |
| 9 | JPY | TONAR_LCH | active | — | — | — | LCH-cleared |
| 10 | NOK | NOWA | active | — | — | — | |
| 11 | NZD | NZIONA | active | — | — | — | |
| 12 | SEK | STINA | active | — | — | — | |
| 13 | SGD | SORA | active | 2023-07-01 | SOR | — | |
| 14 | THB | THOR | active | 2023-07-01 | THBFIX | — | |
| 15 | USD | FEDFUND | active | — | — | — | |
| 16 | USD | SOFR | active | 2023-07-01 | LIBOR | — | |

### OIS Maturities (44 tenors)

1D, 1W, 2W, 3W, 1M–11M, 1Y, 15M, 18M, 21M, 2Y–20Y, 25Y, 30Y, 35Y, 40Y, 45Y, 50Y

---

## SWAP_LIBOR Curves (IBOR-based)

23 curves across G10, Asia, and Other. All use `RATES.SWAP_LIBOR.{CCY}.{QUOTE}.{TENOR}` tag format.

### Active

| # | CCY | Curve | Status | Group | Notes |
|---|-----|-------|--------|-------|-------|
| 1 | AUD | BBSW | active | G10 | Dual-rate market. No cessation planned. |
| 2 | CNH | CNH_HIBOR | active | Asia | |
| 3 | CNY | NDIRS | active | Asia | |
| 4 | CNY | SHIBOR | active | Asia | |
| 5 | EUR | EURIBOR | reformed | G10 | Reformed 2019 (hybrid methodology). No cessation planned. |
| 6 | HKD | HIBOR | active | Asia | No cessation planned. HONIA as RFR alternative. |
| 7 | IDR | JIBOR | active | Asia | |
| 8 | INR | MIFOR | reformed | Asia | Modified MIFOR references SOFR instead of LIBOR since 2023. |
| 9 | KRW | CD | active | Asia | |
| 10 | MYR | KLIBOR | active | Asia | |
| 11 | NOK | NIBOR | active | G10 | Active with NOWA as RFR fallback. |
| 12 | NZD | BKBM | active | G10 | |
| 13 | PHP | PHIREF | active | Asia | |
| 14 | SEK | STIBOR | active | G10 | SWESTR gaining but slow transition. |
| 15 | TWD | TAIBOR | active | Asia | |
| 16 | VND | VND_REF | active | Asia | |

### Ceased

| # | CCY | Curve | Cessation Date | Superseded By | Notes |
|---|-----|-------|---------------|---------------|-------|
| 1 | CAD | CDOR | 2024-06-28 | CORRA | |
| 2 | CHF | CHF_LIBOR | 2021-12-31 | SARON | |
| 3 | GBP | GBP_LIBOR | 2024-03-28 | SONIA | Panel ceased Dec 2021. Synthetic 1M/3M/6M ceased Mar 2024. |
| 4 | JPY | JPY_LIBOR | 2021-12-31 | TONAR | |
| 5 | SGD | SOR | 2023-06-30 | SORA | |
| 6 | THB | THBFIX | 2023-06-30 | THOR | |
| 7 | USD | LIBOR | 2023-06-30 | SOFR | Final panel publication Jun 30, 2023. |

### SWAP_LIBOR Maturities (33 tenors)

1W, 1M–11M, 1Y–20Y, 25Y, 30Y, 40Y, 50Y

---

## Transition Timeline

```
2021-12-31  CHF_LIBOR ceased  →  SARON
2021-12-31  JPY_LIBOR ceased  →  TONAR
2022-01-01  GBP_LIBOR (panel) →  SONIA primary
2022-01-03  EUR EONIA ceased  →  EUROSTR
2023-06-30  USD LIBOR ceased  →  SOFR
2023-06-30  SGD SOR ceased    →  SORA
2023-06-30  THB THBFIX ceased →  THOR
2024-03-28  GBP_LIBOR (synth) →  fully ceased
2024-06-28  CAD CDOR ceased   →  CORRA
```

---

## Quote Types

6 quote types configured in `pipelines.yml` under `rates.historical.default_quotes`:

| Quote | Citi Tag | Description | Multi-tenor |
|-------|----------|-------------|-------------|
| **par** | PAR | Par swap rate | No (1 tenor) |
| **ssw** | SWAP_SPREAD | Swap spread vs government bond | No (1 tenor) |
| **rc** | ROLL_CARRY | Roll and carry | No (1 tenor) |
| **spread** | CURVES | Curve spread (e.g. 2Y vs 10Y) | Yes (2 tenors) |
| **fwd** | FWD | Forward rate (e.g. 5Y5Y) | Yes (2 tenors) |
| **bfly** | BFLY | Butterfly (e.g. 2Y-5Y-10Y) | Yes (3 tenors) |

### Quote Type Availability by Instrument

Not all curves support all quote types. Citi only publishes the full 6 for G10 OIS and major G10 IBOR curves. EM/Asia SWAP_LIBOR curves generally only have **par**.

| Instrument | Region | par | ssw | spread | fwd | bfly | rc |
|------------|--------|-----|-----|--------|-----|------|----|
| OIS | G10 | Yes | Yes | — | — | — | — |
| OIS | Asia | Yes | Yes | — | — | — | — |
| SWAP_LIBOR | G10 | Yes | Yes | — | — | — | — |
| SWAP_LIBOR | Asia/EM | Yes | No | No | No | No | No |

> **Note**: spread/fwd/bfly/rc are requested for all curves but consistently return 0 rows from the Citi API. The pipeline handles this gracefully — empty responses are simply skipped.

---

## Current DB Coverage

As of 2026-03-23. Table: `rates.fact_observation`.

### Date Range

- **Earliest**: 2024-06-03
- **Latest**: 2026-03-20
- **Total rows**: ~403K

### Rows by Curve (par + ssw combined, 2024-06-03 → 2026-03-20)

#### OIS

| CCY | Curve | par rows | ssw rows | Earliest | Latest |
|-----|-------|----------|----------|----------|--------|
| AUD | AONIA | 20,680 | 3,619 | 2024-06-03 | 2026-03-20 |
| CAD | CORRA | 20,680 | 3,572 | 2024-06-03 | 2026-03-20 |
| CHF | SARON | 20,680 | 2,222 | 2024-06-03 | 2026-03-20 |
| EUR | EONIA | 14,164 | 2,423 | 2024-06-03 | 2025-09-08 |
| EUR | EUROSTR | 20,680 | 3,584 | 2024-06-03 | 2026-03-20 |
| GBP | SONIA | 20,680 | 5,028 | 2024-06-03 | 2026-03-20 |
| JPY | TONAR | 19,905 | 5,248 | 2024-06-03 | 2026-03-20 |
| JPY | TONAR_JSCC | 19,905 | 5,248 | 2024-06-03 | 2026-03-20 |
| JPY | TONAR_LCH | 20,680 | 5,248 | 2024-06-03 | 2026-03-20 |
| NOK | NOWA | 20,680 | 1,350 | 2024-06-03 | 2026-03-20 |
| NZD | NZIONA | 20,680 | 3,131 | 2024-06-03 | 2026-03-20 |
| SEK | STINA | 20,680 | 3,188 | 2024-06-03 | 2026-03-20 |
| SGD | SORA | 20,680 | 3,584 | 2024-06-03 | 2026-03-20 |
| THB | THOR | 20,680 | 3,584 | 2024-06-03 | 2026-03-20 |
| USD | FEDFUND | 20,680 | 4,928 | 2024-06-03 | 2026-03-20 |
| USD | SOFR | 20,680 | 4,928 | 2024-06-03 | 2026-03-20 |

#### SWAP_LIBOR — Active

| CCY | Curve | par rows | ssw rows | Earliest | Latest |
|-----|-------|----------|----------|----------|--------|
| AUD | BBSW | 16,920 | 3,171 | 2024-06-03 | 2026-03-20 |
| CNH | CNH_HIBOR | 12,740 | — | 2024-06-03 | 2026-03-20 |
| CNY | NDIRS | 12,236 | — | 2024-06-03 | 2026-03-20 |
| CNY | SHIBOR | 12,236 | — | 2024-06-03 | 2026-03-20 |
| EUR | EURIBOR | 16,911 | 896 | 2024-06-03 | 2026-03-20 |
| HKD | HIBOR | 13,160 | — | 2024-06-03 | 2026-03-20 |
| IDR | JIBOR | 12,376 | — | 2024-06-03 | 2026-03-17 |
| INR | MIFOR | 12,320 | — | 2024-06-03 | 2026-03-20 |
| KRW | CD | 16,620 | — | 2024-06-03 | 2026-03-20 |
| MYR | KLIBOR | 13,160 | — | 2024-06-03 | 2026-03-20 |
| NOK | NIBOR | 16,878 | 1,350 | 2024-06-03 | 2026-03-20 |
| NZD | BKBM | 16,920 | 2,235 | 2024-06-03 | 2026-03-20 |
| PHP | PHIREF | 12,208 | — | 2024-06-03 | 2026-03-19 |
| SEK | STIBOR | 16,820 | 1,396 | 2024-06-03 | 2026-03-20 |
| TWD | TAIBOR | 13,068 | — | 2024-06-03 | 2026-03-20 |
| VND | VND_REF | 12,572 | — | 2024-06-03 | 2026-03-20 |

#### SWAP_LIBOR — Ceased (Historical Only)

| CCY | Curve | par rows | ssw rows | Earliest | Latest | Cessation |
|-----|-------|----------|----------|----------|--------|-----------|
| CAD | CDOR | 6,840 | 712 | 2024-06-03 | 2025-02-21 | 2024-06-28 |
| CHF | CHF_LIBOR | 6,696 | 11 | 2024-06-03 | 2025-02-21 | 2021-12-31 |
| GBP | GBP_LIBOR | 6,840 | 1,302 | 2024-06-03 | 2025-02-21 | 2024-03-28 |
| JPY | JPY_LIBOR | 6,300 | 1,380 | 2024-06-03 | 2025-02-21 | 2021-12-31 |
| SGD | SOR | 5,068 | — | 2024-06-03 | 2025-02-21 | 2023-06-30 |
| THB | THBFIX | — | — | — | — | 2023-06-30 |
| USD | LIBOR | 6,731 | 1,432 | 2024-06-03 | 2025-02-21 | 2023-06-30 |

> **Note on ceased curves**: Citi continues to return historical par data for ceased IBOR curves even for dates well past cessation (e.g. CDOR data through 2025-02-21 despite cessation 2024-06-28). This likely represents synthetic/fallback rate calculations.

---

## Not Yet In Universe (Listed in instruments but no curve catalog entry)

These currencies appear in `rates.yml` under `instruments.swap_libor.currencies` but have no `curves:` entry, so the pipeline does not fetch them:

AED, ARS, BDT, BRL, CLP, COP, CZK, DKK, EGP, HUF, ILS, KZT, LKR, MXN, NGN, PLN, RON, RUB, SAR, TRY, ZAR

Adding these would require new curve catalog entries in `rates.yml` with the correct Citi tag prefix.

---

## Swaption Vol (Separate Pipeline)

See [swaption_vol_schema.md](swaption_vol_schema.md) and [swaption_vol_operations.md](swaption_vol_operations.md).

- 11 currencies: AUD, CHF, DKK, EUR, GBP, JPY, KRW, NOK, NZD, SEK, USD
- 6 data types: ATM, ATM_RFR, REALIZED, REALIZED_RFR, VOL_RATIO, VOL_RATIO_RFR
- Table: `rates.fact_swaption_vol` + `rates.dim_vol_surface`
- ~38K tags, ~24K rows/day
