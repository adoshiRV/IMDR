# Rates Swaption Vol — Schema Reference

Swaption vol surfaces from Citi Velocity. 38,056 tags across 11 currencies, covering ATM implied (Black + Normal), realized, and implied/realized ratio.

For the full rates schema (dim_curve, fact_observation), see [`rates_schema.md`](rates_schema.md).

---

## Tag Structure

```
RATES.VOL.{CCY}.{DATA_TYPE}.{...qualifiers...}.{OPTION_EXPIRY}.{SWAP_TENOR}
```

| Data Type | Tag Depth | Qualifier Fields | Example |
|-----------|-----------|------------------|---------|
| ATM | 7 | quote_type | `RATES.VOL.USD.ATM.BLACK.5Y.10Y` |
| ATM_RFR | 7 | quote_type | `RATES.VOL.USD.ATM_RFR.NORMAL.5Y.10Y` |
| REALIZED | 8 | vol_window, freq | `RATES.VOL.USD.REALIZED.1M.ANNUAL.5Y.10Y` |
| REALIZED_RFR | 8 | vol_window, freq | `RATES.VOL.EUR.REALIZED_RFR.3M.DAILY.5Y.10Y` |
| VOL_RATIO | 7 | vol_window | `RATES.VOL.USD.VOL_RATIO.1M.5Y.10Y` |
| VOL_RATIO_RFR | 7 | vol_window | `RATES.VOL.EUR.VOL_RATIO_RFR.3M.5Y.10Y` |

---

## Data Types Explained

| Data Type | What It Is | Units | Use Case |
|-----------|-----------|-------|----------|
| **ATM** | At-the-money swaption implied vol | BLACK = annualized %, NORMAL = bps/yr | Core vol surface for pricing, risk |
| **ATM_RFR** | Same as ATM but referencing RFR swaps | Same | Post-LIBOR transition pricing |
| **REALIZED** | Historical swap rate volatility | Annualized % or daily | Implied vs realized comparison |
| **VOL_RATIO** | Implied / Realized ratio | Dimensionless (>1 = rich) | Richness/cheapness indicator |

**Quote types** (ATM/ATM_RFR only):
- **BLACK**: Log-normal vol (annualized %). Standard for most currencies.
- **NORMAL**: Bachelier vol (bps/year). Used for JPY/EUR where rates can go negative.
- **PREMIUM**: Option premium in rate terms.
- **FWDPREMIUM**: Forward-adjusted premium.

---

## Grids

- **Option expiries (15)**: 1M, 3M, 6M, 9M, 1Y, 2Y, 3Y, 4Y, 5Y, 7Y, 10Y, 12Y, 15Y, 20Y, 30Y
- **Swap tenors (10)**: 3M, 1Y, 2Y, 3Y, 5Y, 7Y, 10Y, 15Y, 20Y, 30Y
- **Realized windows (4)**: 1M, 3M, 6M, 1Y
- **Realized freqs (2)**: ANNUAL, DAILY

---

## Currency Coverage

| Currency | Has RFR? | Tags |
|----------|----------|------|
| USD | Yes | 4,695 |
| JPY | Yes | 4,525 |
| EUR | Yes | 4,457 |
| GBP | Yes | 4,457 |
| CHF | Yes | 4,442 |
| AUD | No | 2,590 |
| KRW | No | 2,590 |
| NZD | No | 2,590 |
| DKK | No | 2,560 |
| NOK | No | 2,575 |
| SEK | No | 2,575 |
| **TOTAL** | | **38,056** |

---

## Database Tables

### `[rates].[dim_vol_surface]`

See [`rates_schema.md`](rates_schema.md) for column-level detail.

Inapplicable qualifier fields use empty string `''` (not NULL):
- ATM row: `quote_type='BLACK'`, `vol_window=''`, `freq=''`
- REALIZED row: `quote_type=''`, `vol_window='1M'`, `freq='ANNUAL'`
- VOL_RATIO row: `quote_type=''`, `vol_window='1M'`, `freq=''`

### `[rates].[fact_swaption_vol]`

See [`rates_schema.md`](rates_schema.md) for column-level detail.

---

## Sample Queries

```sql
-- USD ATM Black vol surface for a specific date
SELECT s.ccy, v.option_expiry, v.swap_tenor, v.value
FROM [rates].[fact_swaption_vol] v
JOIN [rates].[dim_vol_surface] s ON v.surface_id = s.id
WHERE s.ccy = 'USD' AND s.data_type = 'ATM' AND s.quote_type = 'BLACK'
  AND v.obs_date = '2026-03-17'
ORDER BY v.option_expiry, v.swap_tenor;

-- Compare implied vs realized for USD 5Y10Y
SELECT v.obs_date, s.data_type, s.quote_type, s.vol_window, v.value
FROM [rates].[fact_swaption_vol] v
JOIN [rates].[dim_vol_surface] s ON v.surface_id = s.id
WHERE s.ccy = 'USD'
  AND v.option_expiry = '5Y' AND v.swap_tenor = '10Y'
  AND s.data_type IN ('ATM', 'REALIZED')
  AND (s.quote_type = 'BLACK' OR s.vol_window = '3M')
ORDER BY v.obs_date, s.data_type;

-- Vol ratio time series (is swaption vol rich or cheap?)
SELECT v.obs_date, v.value AS vol_ratio
FROM [rates].[fact_swaption_vol] v
JOIN [rates].[dim_vol_surface] s ON v.surface_id = s.id
WHERE s.ccy = 'USD' AND s.data_type = 'VOL_RATIO' AND s.vol_window = '3M'
  AND v.option_expiry = '1Y' AND v.swap_tenor = '10Y'
ORDER BY v.obs_date;

-- Row counts per currency per date
SELECT s.ccy, v.obs_date, COUNT(*) AS n_obs
FROM [rates].[fact_swaption_vol] v
JOIN [rates].[dim_vol_surface] s ON v.surface_id = s.id
GROUP BY s.ccy, v.obs_date
ORDER BY v.obs_date DESC, s.ccy;
```

---

## Quality Ranges

Configured in `src/imdr/universe/rates.yml` under `vol.quality.ranges`:

| Key | Min | Max | Notes |
|-----|-----|-----|-------|
| ATM.BLACK | 0.1 | 200.0 | Log-normal vol (%) |
| ATM.NORMAL | 1.0 | 500.0 | Bachelier vol (bps/yr) |
| ATM.PREMIUM | 0.0 | 50.0 | Option premium |
| ATM.FWDPREMIUM | 0.0 | 50.0 | Forward premium |
| REALIZED | 0.0 | 200.0 | Realized vol |
| VOL_RATIO | 0.0 | 5.0 | Implied/realized ratio |
