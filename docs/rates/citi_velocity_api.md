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
