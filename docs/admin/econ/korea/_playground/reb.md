# REB R-ONE — `playground/econ/reb/`

**Status:** LIVE (2026-06-04). 4 indicators × 2,928 obs in `econ.fact_indicator`. Migration 078 added the `reb` vendor row.

Korea Real Estate Board R-ONE Open API. Distinct vendor from KOSIS (issued via data.go.kr service id 15134761), but covers the same weekly apartment indices with 11 extra years of history (2012-05-07 → present vs KOSIS mirror's 2021-07 →).

## Contents

- **`fetch_housing.py`** — pulls 4 weekly apartment indices: sale price (`T244183132827305`) and jeonse price (`T247713133046872`), each cut by `CLS_ID` for 전국 (`50001`) + 서울 (`50008`).
- **`sample_output/`** — date-tree parquet output, consumed by the canonical loader.

## API quirks (vs KOSIS)

| Behaviour | KOSIS | REB |
|---|---|---|
| TLS pinning | TLS 1.2 required (handshake reset on 1.3) | TLS 1.3 negotiates fine |
| Per-call cap | 40,000 rows | 1,000 rows (`pSize`) hard cap |
| Date filter | Honoured | **Required but ignored server-side** — pass to avoid `ERROR-300`, full series returns regardless |
| Auth env var | `IMDR_KOSIS_API_KEY` (44-char base64) | `IMDR_REB_API_KEY` (32-char hex) |
| Response shape | Flat list | `{"SttsApiTblData":[{"head":[…]},{"row":[…]}]}` |

## Naming convention

REB-direct rows use **`.REB_DIRECT` imdr_code suffix** to coexist with KOSIS-mirror rows under the `uq_dim_indicator_imdr_code` UNIQUE constraint. Both sources live in `econ.dim_indicator`:
- REB-direct: 2012-05-07 → present (14 yrs weekly)
- KOSIS mirror: 2021-07 → present (5 yrs weekly)

## Reconciliation

Confirmed 0 bp YoY drift vs KOSIS mirror across 3 anchor weeks (2025-06-02, 2025-12-29, 2026-01-26). Levels differ (REB base 2026-02-02=100, KOSIS base 2025-03-31=100) but YoY % change is identical — same underlying published series.

## Catalogue

- 738 tables total in REB R-ONE catalogue.
- 8 are weekly (`DTACYCLE_CD="WK"`), all under `T2…` prefix.
- Other cadences (`MM`, `QQ`, `YY`) not yet probed.

See [[reb-rone-openapi-live]] memory for full quirks reference.
