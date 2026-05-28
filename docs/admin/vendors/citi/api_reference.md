# Citi Velocity API Reference

Developer-facing reference for the Citi Velocity rates data API, as implemented in `connectors/citi_velocity.py`.

---

## Endpoints

| # | Endpoint | Method | Path | Purpose |
|---|---|---|---|---|
| 1 | **Token** | POST | `/markets/cv/api/oauth2/token` | OAuth2 client_credentials → Bearer token |
| 2 | **Historical** | POST | `/markets/analytics/chartingbe/rest/external/authed/data` | Time series data by tag |
| 3 | **Metadata** | POST | `/markets/analytics/chartingbe/rest/external/authed/data` | Series metadata (modification times, ranges) |
| 4 | **Tag Listing** | POST | `/markets/analytics/chartingbe/rest/external/authed/taglisting` | List tags by prefix + optional regex |
| 5 | **Tag Browsing** | POST | `/markets/analytics/chartingbe/rest/external/authed/tagbrowsing` | Explore tag tree hierarchy |

All non-token endpoints append `?client_id={id}` to the URL and use Bearer auth headers.

---

## Authentication

**Flow:** OAuth2 `client_credentials` grant

```
POST /markets/cv/api/oauth2/token
Content-Type: application/x-www-form-urlencoded

grant_type=client_credentials&client_id={ID}&client_secret={SECRET}&scope=/api
```

**Response:**
```json
{"access_token": "eyJ...", "expires_in": 3600, "token_type": "Bearer"}
```

**Token management:**
- TTL: 3600 seconds (1 hour)
- Auto-refresh: 60 seconds before expiry
- Cached in `CitiVelocityClient` — no manual token passing needed

**Settings (`.env`):**
```
IMDR_CITI_CLIENT_ID=your_client_id
IMDR_CITI_CLIENT_SECRET=your_client_secret
```

---

## Historical Data API

**Request:**
```json
POST /data?client_id={ID}
Authorization: Bearer {token}

{
  "startDate": 20240101,
  "endDate": 20240131,
  "startTime": 0,
  "endTime": 2359,
  "tags": ["RATES.OIS.USD_SOFR.PAR.5Y", "RATES.OIS.USD_SOFR.PAR.10Y"],
  "frequency": "DAILY"
}
```

**Response:**
```json
{
  "status": "OK",
  "body": {
    "RATES.OIS.USD_SOFR.PAR.5Y": {
      "type": "LINE",
      "x": [20240102, 20240103, 20240104],
      "c": [3.85, 3.87, 3.82]
    },
    "RATES.OIS.USD_SOFR.PAR.10Y": {
      "type": "LINE",
      "x": [20240102, 20240103],
      "c": [4.12, 4.15]
    }
  }
}
```

**Limits:** 1–100 tags per request. Batched automatically by `CitiVelocityRatesExtractor`.

### X-Axis Timestamp Formats

| Digits | Format | Example | Parsed As |
|---|---|---|---|
| 6 | `YYYYMM` | `202401` | 2024-01-01 (monthly) |
| 8 | `YYYYMMDD` | `20240115` | 2024-01-15 (daily) |
| 10 | `YYYYMMDDHH` | `2024011514` | 2024-01-15 14:00 (hourly) |
| 11 | `YYYYMMDDHHm` | `20240115143` | 2024-01-15 14:30 (ten-minutely) |
| 12 | `YYYYMMDDHHMM` | `202401151430` | 2024-01-15 14:30 (minutely) |

Parsed by `domains/rates/utils.py:parse_x_to_ts_utc()`.

---

## Tag Structure

### OIS Tags
```
RATES.OIS.{CCY}_{INDEX}.{QUOTE_TYPE}.{MATURITY}
```

| Part | Example | Description |
|---|---|---|
| CCY_INDEX | `USD_SOFR` | Currency + overnight rate index |
| QUOTE_TYPE | `PAR` | See quote types table |
| MATURITY | `5Y` | Single tenor |

Multi-tenor tags:
- **CURVES (spread):** `RATES.OIS.USD_SOFR.CURVES.2Y.10Y` (6 parts)
- **FWD:** `RATES.OIS.USD_SOFR.FWD.5Y.5Y` (6 parts)
- **BFLY:** `RATES.OIS.USD_SOFR.BFLY.2Y.5Y.10Y` (7 parts)

Multi-tenor combos are defined in `multi_tenor_combos` in `rates.yml` and used by `build_tags()` (API probe: ~1,156 FWD / ~1,936 CURVES / ~2,600 BFLY tags per OIS curve).

### SWAP_LIBOR Tags
```
RATES.SWAP_LIBOR.{CCY}.{QUOTE_TYPE}.{MATURITY}
```

No index component — just currency. Same multi-tenor patterns apply.

**Special case:** `CNY_NDIRS` — underscore in the currency part: `RATES.SWAP_LIBOR.CNY_NDIRS.PAR.5Y`

---

## Tag Listing

**Request:**
```json
POST /taglisting?client_id={ID}
Authorization: Bearer {token}

{"prefix": "RATES.OIS.USD_SOFR.PAR"}
```

**Response:**
```json
{
  "status": "OK",
  "tags": ["RATES.OIS.USD_SOFR.PAR.1D", "RATES.OIS.USD_SOFR.PAR.1W", ...]
}
```

- Minimum 2-level prefix (e.g. `RATES.OIS.`)
- Optional `regex` field for Java regex filtering against full tag
- Used by `RatesTagDiscovery.fetch_all_par_tags()`

---

## Tag Browsing

**Request:**
```json
POST /tagbrowsing?client_id={ID}
Authorization: Bearer {token}

{"prefix": "RATES"}
```

**Response:**
```json
{
  "status": "OK",
  "header": "RATES",
  "fields": {"OIS": {}, "SWAP_LIBOR": {}},
  "leaves": []
}
```

Pass `""` for root level. Drill down one level at a time.

---

## Full Tag Tree (Discovered 2026-03-11)

Root-level categories: `COMMODITIES`, `EQUITY`, `FX`, `RATES`

### All RATES Subcategories (28)

Discovered via `scripts/explore/explore_rates_categories.py`. Full tree cached at `data/cache/rates/rates_tree.json`.

#### Currently Tracked

| Subcategory | Tag Pattern | Children | Description |
|---|---|---|---|
| **OIS** | `RATES.OIS.{CCY}_{INDEX}.{QT}.{MAT}` | 20 ccy/index pairs | OIS swap rates (RFR) |
| **SWAP_LIBOR** | `RATES.SWAP_LIBOR.{CCY}.{QT}.{MAT}` | 45 currencies | IBOR swap rates |

#### High Priority — Core Rates Data

| Subcategory | Tag Pattern | Children | Description |
|---|---|---|---|
| **SOV_CMT** | `RATES.SOV_CMT.{COUNTRY}.{MAT}` | 34 countries | Sovereign constant-maturity yields (full tenor grid 1M–50Y) |
| **SOV** | `RATES.SOV.{COUNTRY}.{QT}.{MAT}` | 21 countries | Sovereign on-the-run yields (OTR, OTR_OLD, CURVES, BFLY) |
| **TSY** | `RATES.TSY.{QT}.{MAT}` | 5 sub-types | US Treasury yields (OTR, CMT, CURVES, BFLY, OLD_1) |
| **T_BILL** | `RATES.T_BILL.OTR.{MAT}` | 1 (OTR) | US T-Bill rates (1M, 3M, 6M, 1Y) |
| **XCCY_SWAP** | `RATES.XCCY_SWAP.{CCY}.USD.{MAT}` | 23 ccys | Cross-currency basis swaps (IBOR-based, vs USD) |
| **XCCY_OIS_SWAP** | `RATES.XCCY_OIS_SWAP.{CCY}.{CCY2}.{MAT}` | 12 ccys | Cross-currency OIS basis (RFR-based, G10 cross pairs) |
| **BASIS_SWAPS** | `RATES.BASIS_SWAPS.{TYPE}.{CCY}.{MAT}` | 6 types | Tenor basis: 3s1s, 3s6s, 3s-OIS, SOFR-FF, SOFR-LIBOR, EUROSTR-EURIBOR |
| **BENCH_RATES** | `RATES.BENCH_RATES.{NAME}` | 10 series (leaf tags) | Central bank policy rates: Fed Funds, ECB, BoE base, BoJ target/discount, Fed CP/Prime |
| **VOL** | `RATES.VOL.{CCY}.{TYPE}.{MAT}` | 11 ccys | Swaption vol: ATM, REALIZED, VOL_RATIO (some have _RFR variants) |
| **INFLATION** | `RATES.INFLATION.{TYPE}.{INDEX}.{MAT}` | 4 sub-types | Inflation swaps (17 indices), indices (5), carry (6 ccys), swaptions |

#### Medium Priority

| Subcategory | Tag Pattern | Children | Description |
|---|---|---|---|
| **MONEY_MARKETS** | `RATES.MONEY_MARKETS.{CCY}.{INDEX}.{MAT}` | 9 ccys | Short-term fixings: BBSW, LIBOR, etc. (AUD, CAD, CHF, EUR, GBP, JPY, NOK, SEK, USD) |
| **FRA** | `RATES.FRA.{CCY}.{MAT}` | 9 EM ccys | Forward Rate Agreements: CLP, COP, CZK, HUF, ILS, KRW, MXN, PLN, ZAR |
| **FRA_OIS** | `RATES.FRA_OIS.{CCY}.{DATE}` | 11 G10 ccys | OIS FRA (meeting-dated, e.g. `12_MAR_2026Y`) |
| **OIS_MEETING** | `RATES.OIS_MEETING.{CCY}.{YEAR}.{DATE}` | 10 ccys | Central bank meeting-dated OIS (data from 2020+) |
| **FORWARD** | `RATES.FORWARD.{COUNTRY}.{MAT}` | 24 countries | Sovereign forward yields (2Y, 5Y, 8Y, 10Y, 20Y, 30Y) |
| **TIPS** | `RATES.TIPS.{TYPE}.{MAT}` | 2 (USD, EXT_POLATED) | US TIPS yields: 5Y, 10Y, 30Y + extrapolated 10Y |
| **FORECAST** | `RATES.FORECAST.{NAME}.{FREQ}` | 7 series | Citi rate forecasts: Fed Funds, ECB, UST/GER/JGB/UK 10Y (QTR, ANNUAL) |
| **INVOICESPREAD** | `RATES.INVOICESPREAD.{CCY}.{MAT}` | 2 (USD, USD_BACKMONTH) | Bond futures invoice spreads: 2Y, 3Y, 5Y, 10Y, Ultra10Y, Ultra30Y, UltraBond |

#### Specialized / Niche

| Subcategory | Children | Description |
|---|---|---|
| **OIS_INVOICESPREAD** | 24 (EUR futures + USD SOFR/FF) | Invoice spreads vs OIS for EUR bond futures and USD SOFR/FedFund |
| **SSA** | 19 issuers (KFW, EIB, IBRD, etc.) | Supranational/Agency bond spreads (SPOT quotes) |
| **SSA_CS** | 22 issuers | SSA credit spreads (EUR_USD cross-currency) |
| **MBS** | 13 sub-types | Mortgage-backed securities: butterflies, coupon swaps, rates, performance, options |
| **MIDCURVES** | 5 (EUR, EURIBOR, GBP, USD, USD_SOFR) | Swaption mid-curve vol (OPT_PAY, OPT_REC, OPT_STR) |
| **SPREAD_OPTIONS** | 2 (EUR, USD) | Spread option vol (OPT_CAP, OPT_FLR, OPT_STR) |
| **POS_MON** | 8 countries | Position monitor (10Y only: AUS, CAN, DEU, FRA, GBR, ITA, JPN, USA) |
| **AGENCY_INVENTORY** | 3 (BULLET_DURATION, BULLET_MATURITY, UST_MATURITY) | Agency callable inventory (BERM, EUROPEAN) |

### Country Codes Used in Sovereign Tags

| Code | Country | Code | Country | Code | Country |
|---|---|---|---|---|---|
| AUS | Australia | ESP | Spain | JPN | Japan |
| AUT | Austria | FIN | Finland | LUX | Luxembourg |
| BEL | Belgium | FRA | France | NLD | Netherlands |
| CAN | Canada | GBR | United Kingdom | NOR | Norway |
| CHE | Switzerland | GRC | Greece | NZL | New Zealand |
| CYP | Cyprus | HUN | Hungary | POL | Poland |
| CZE | Czech Republic | IRL | Ireland | PRT | Portugal |
| DEU | Germany | ISR | Israel | ROU | Romania |
| DNK | Denmark | ITA | Italy | SWE | Sweden |
| | | | | USA | United States |

Additional in SOV_CMT only: RUS, SVK, SVN, TUR, ZAF

---

## Rate Limits

| Limit | Value |
|---|---|
| Requests per second | 1 |
| Max concurrent connections | 1 |
| Tags per historical request | 100 |
| Max daily API calls | 10,000 |
| Token TTL | 3,600 seconds |

The extractor enforces `citi_rate_limit_sec` (default 1.0s) between batches.

---

## Error Handling

| Scenario | Behavior |
|---|---|
| HTTP >= 400 | `RuntimeError` with status code and response body |
| Non-JSON response | `RuntimeError` with first 500 chars |
| `type: "ERROR"` in body | Tag silently skipped (logged) |
| `status != "OK"` in response | `RuntimeError` |
| Token expired mid-request | Auto-refresh on next call (60s buffer) |
| Rate limit exceeded | Respect `citi_rate_limit_sec` between batches |

The httpx transport retries 3 times for connection-level failures.
