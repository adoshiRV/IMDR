# FX Calendar Integration

## FX Market Hours

FX is a 24-hour OTC market running from Sunday 21:00 UTC to Friday 21:00 UTC. This is fundamentally different from equity-style exchange hours.

The existing `FXUniverse.is_fx_open(dt)` in `src/imdr/universe/fx.py` handles this:

```python
from imdr.universe.fx import get_fx_universe
universe = get_fx_universe()
universe.is_fx_open(utc_dt)  # True if within Sun 21:00 - Fri 21:00 UTC
```

The calendar module's `is_market_open()` handles equity-style hours. For FX, continue using `is_fx_open()`.

## Holiday Impacts on FX

While FX markets technically trade 24h, holidays affect liquidity and data availability:

- **Settlement holidays** — trades may not settle if a currency's settlement center is closed
- **Partial holidays** — one leg of a pair may have a holiday (e.g., US holiday = reduced USD liquidity)
- **Data gaps** — Citi Velocity may not publish vol surfaces on holidays

The calendar module's `holiday_hits_for_timestamp()` identifies which currencies are affected:

```python
from imdr.market_calendar import holiday_hits_for_timestamp

hits = holiday_hits_for_timestamp(["USD", "EUR", "JPY"], utc_dt)
for h in hits:
    print(f"{h.currency} ({h.market_code}): {h.name}")
```

## EOD Scheduling

FX vol and spot scripts use `last_business_day("US")` since they run on the US daily schedule:

```python
from imdr.market_calendar import last_business_day
target = last_business_day("US")
```

## Health Check Relaxation

On non-trading days, FX health checks should expect no new data:

```python
from imdr.healthchecks.quality import should_relax_checks

if should_relax_checks(run_date, market_code="US"):
    # Row count minimum -> 0, freshness -> extended
    pass
```

## Currency-to-Market Mapping

| FX Group | Currencies | Markets |
|----------|-----------|---------|
| G10 | USD, EUR, GBP, JPY, CHF, AUD, NZD, CAD, NOK, SEK, CNH | US, EU, UK, JP, CH, AU, NZ, CA, NO, SE, CN |
| EM NDF | INR, KRW, TWD, THB, IDR, PHP | IN, KR, TW, TH, ID, PH |
| EM Deliverable | SGD | SG |

Note: CNH (offshore Yuan) maps to the CN market. While offshore CNH trades globally, settlement holidays follow mainland China's calendar.
