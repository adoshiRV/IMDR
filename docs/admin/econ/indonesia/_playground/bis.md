# BIS — Pre-prod playground notes

Last updated: 2026-06-09

Companion to [`bps.md`](bps.md) and [`bi.md`](bi.md). Third Indonesia
vendor (Tier-4 cross-country fallback per the
[onboarding playbook](../../onboarding_new_country.md#step-2--resolve-each--via-the-vendor-cascade))
covering harmonised macro-financial gauges that the native publishers
either don't compute (DSR / Credit-to-GDP gap) or compute on a per-
country basis that's hard to compare (effective exchange rates).

## Playground location

```
playground/econ/bis/
├── _bis_sdmx.py        ← SDMX-JSON fetcher + period-string parser
├── _bis_common.py      ← shared CLI / parquet / summarize (mirrors _bi_common)
├── fetch_indonesia.py  ← all-in-one BIS Indonesia fetcher (8 series)
└── sample_output/      ← parquet outputs
```

## Source URL pattern

```
https://stats.bis.org/api/v2/data/dataflow/BIS/{flow_id}/{version}/{key}
```

Headers required:
```
Accept: application/vnd.sdmx.data+json;version=1.0.0
```

No auth. Public. Polite throttle 1 s/request (default in `_bis_sdmx.py`).

## BIS dataflows used for Indonesia

| Dataflow | Topic | Key format | Notes |
|---|---|---|---|
| `WS_EER` | Effective Exchange Rates | `FREQ.EER_TYPE.EER_BASKET.REF_AREA` | Indonesia uses 2-letter `ID` |
| `WS_DSR` | Debt Service Ratios | `FREQ.BORROWERS_CTY.DSR_BORROWERS` | EM countries (incl. ID) only publish `P` (PNFS aggregate); H + N return 404 |
| `WS_CREDIT_GAP` | Credit-to-GDP ratio / trend / gap | `FREQ.BORROWERS_CTY.TC_BORROWERS.TC_LENDERS.CG_DTYPE` | CG_DTYPE: A=ratio, B=HP-trend, C=gap |
| `WS_CBPOL` | Central bank policy rates | `FREQ.REF_AREA` | Daily; BI 7-Day RR Rate |

## Discovered dataflow inventory (29 total)

The full list is available at
`https://stats.bis.org/api/v2/structure/dataflow/BIS/all/latest`. Other
flows considered but not used for Indonesia:

| Dataflow | Why deferred |
|---|---|
| `WS_TC` (Total Credit) | Returned 404 on plain key probe; needs longer key (probably TC_BORROWERS+TC_LENDERS+UNIT_TYPE) — redundant with WS_CREDIT_GAP for our purposes |
| `WS_LBS_*` (Locational Banking) | Cross-country banking flows; useful for BoP-cross-validation but BI BoP already covers Indonesia |
| `WS_DER_OTC_TOV` (OTC derivatives turnover) | Belongs in rates/FX domain, not econ |
| `WS_PP_*` (Property Prices) | BIS doesn't publish for Indonesia |
| `WS_NA_SEC_C3` (Securities statistics) | Out-of-scope for the 16-cell wiring map |

## Indonesia coverage shipped (Phase D4)

| Indicator | n | Window | Latest | Source key |
|---|:---:|---|:---:|---|
| `BIS.NEER.BROAD.ID` | 388 | 1994-01 → 2026-04 | 89.83 | WS_EER M.N.B.ID |
| `BIS.REER.BROAD.ID` | 388 | 1994-01 → 2026-04 | 91.44 | WS_EER M.R.B.ID |
| `BIS.DSR.PNFS.ID` | 107 | 1999-Q1 → 2025-Q3 | 4.4% | WS_DSR Q.ID.P |
| `BIS.CREDIT_TO_GDP.RATIO.ID` | 199 | 1976-Q1 → 2025-Q3 | 39.8% | WS_CREDIT_GAP Q.ID.P.A.A |
| `BIS.CREDIT_TO_GDP.GAP.ID` | 159 | 1986-Q1 → 2025-Q3 | -1.3 pp | WS_CREDIT_GAP Q.ID.P.A.C |
| `BIS.POLICY_RATE.ID` | 7,570 | 2005-07 → 2026-04 | 4.75% | WS_CBPOL D.ID |
| **TOTAL** | **8,811** | | | |

**Note**: `Q.ID.H` (Household DSR) and `Q.ID.N` (Non-fin Corp DSR) both
return 404 — BIS only publishes the aggregate `P` (Private non-financial
sector) for emerging markets including Indonesia. Per-borrower-type
splits would need OJK / native sources.

## SDMX-JSON parsing notes

Response shape (single-series query):
```json
{
  "data": {
    "dataSets": [
      {
        "series": {
          "0:0:0:0": {
            "observations": {
              "0": [89.83, 0],
              "1": [89.55, 0],
              ...
            }
          }
        }
      }
    ],
    "structure": {
      "dimensions": {
        "observation": [
          {"id": "TIME_PERIOD", "values": [
            {"id": "2026-01"}, {"id": "2026-02"}, ...
          ]}
        ],
        "series": [
          {"id": "FREQ", "values": [{"id": "M"}]},
          {"id": "EER_TYPE", "values": [{"id": "N"}]},
          ...
        ]
      }
    }
  }
}
```

- `dataSets[0].series` is keyed by `:`-joined series-dim positions
- Each `observations` value is `[value, status_code, ...]` — first element is the number
- `observations[obs_position]` is looked up against `structure.dimensions.observation[0].values[obs_position].id` to get the time-period string
- Time-period format depends on `FREQ`:
  - `D` → `YYYY-MM-DD`
  - `M` → `YYYY-MM`
  - `Q` → `YYYY-Q{1..4}`
  - `A` → `YYYY`

`_bis_sdmx.parse_bis_period()` handles all four; returns `datetime.date` anchored at the period START (Q1 → Jan 1, etc.).

## Adding a new BIS country

1. Find country's 2-letter code (Indonesia=`ID`, Korea=`KR`, India=`IN`, etc. — verify in dimension catalogue).
2. Add per-country fetcher (mirror `fetch_indonesia.py`) OR extend `_TARGETS` if same vendor.
3. Verify which dataflows cover that country — EM countries often have fewer DSR / Credit-Gap series than DM.
4. No new migration needed if `vendor_code='bis'` already exists.

## Deferred

- WS_TC Total Credit — would need longer-key probe + understand TC_BORROWERS/TC_LENDERS/UNIT_TYPE combinations
- WS_LBS — cross-border banking flows (for BoP cross-validation)
- DM-only series (HH DSR, Property Prices) — not available for Indonesia

## Cross-refs

- [`bps.md`](bps.md) — BPS playground notes (primary Indonesia source, API-grade)
- [`bi.md`](bi.md) — BI SEKI playground notes (second Indonesia source, XLSX)
- [`../index.md`](../index.md) — Indonesia landing page
- [`../id_coverage_plan.md`](../id_coverage_plan.md) — cell ↔ vendor mapping
