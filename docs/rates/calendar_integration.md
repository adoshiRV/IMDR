# Rates Calendar Integration

## EOD Scheduling

Rates pipelines use `last_business_day("US")` to determine the target date for daily EOD ingestion. This is holiday-aware — it skips US federal holidays and weekends, not just Sat/Sun.

```python
from imdr.market_calendar import last_business_day

target = last_business_day("US")  # Most recent US trading day
```

The live scripts (`rates_citi_live.py`, `rates_vol_citi_live.py`) import this directly from the calendar module instead of maintaining local copies.

## Settlement Calendars (ISDA)

For rates/swaps, settlement depends on the ISDA financial centers of the currencies involved. A swap between USD and EUR settles on a day that is a business day in both USNY and EUTA (TARGET).

```python
from imdr.market_calendar import is_settlement_holiday, isda_holidays

# Check if a date is a settlement holiday for US
is_settlement_holiday("US", date(2026, 7, 3))  # True (Independence Day observed)

# Get all NYSE settlement holidays for 2026
nyse_hols = isda_holidays("NYSE", 2026)
```

### ISDA Centers by Rates Currency

| Currency | Market | ISDA Centers | Notes |
|----------|--------|-------------|-------|
| USD | US | NYSE, XNYS | Primary settlement center |
| EUR | EU | ECB, TAR, XECB | TARGET2 system |
| GBP | UK | IFEU | ICE Futures Europe |
| INR | IN | BSE, NSE, XBOM, XNSE | Bombay/National Stock Exchange |
| BRL | BR | B3, BVMF | B3 Exchange |
| JPY, CHF, AUD, etc. | Various | - | Use country holidays (no ISDA center in library) |

## Central Bank Events

Rate decisions are the most impactful CB events for rates markets. After importing from the Bloomberg Excel:

```python
from imdr.market_calendar.cb_events import rate_decisions, upcoming_cb_events

# High-relevance rate decisions in the next 90 days
with Session(connector.engine) as session:
    decisions = rate_decisions(session, market_code="US")
    for d in decisions:
        print(f"{d.event_date}: {d.event} (actual: {d.actual})")
```

Key rate decision events by market:
- **US**: FOMC Rate Decision (Upper/Lower Bound) — `FDTR Index`
- **EU**: ECB Main Refinancing Rate — via category "Central Banks" with EC country code
- **JP**: BOJ Target Rate — `BOJDTR Index`
- **AU**: RBA Cash Rate Target — `RBATCTR Index`
- **KR**: BOK Base Rate — `KORP7DR Index`
- **IN**: RBI Repurchase Rate
- **NZ**: RBNZ Official Cash Rate — `NZOCR Index`

## IMM Dates

IMM dates (3rd Wednesday) are significant for swap rolls and futures expiry:

```python
from imdr.market_calendar import imm_dates_quarterly, next_imm_date, is_imm_date

# Quarterly roll dates for 2026
for d in imm_dates_quarterly(2026):
    print(d)  # 2026-03-18, 2026-06-17, 2026-09-16, 2026-12-16

# Next quarterly IMM
next_q = next_imm_date(quarterly_only=True)
```

## Currency-to-Market Mapping

All rates universe currencies and their calendar markets:

| Group | Currencies | Markets |
|-------|-----------|---------|
| G10 | USD, EUR, GBP, JPY, CHF, AUD, NZD, CAD, NOK, SEK | US, EU, UK, JP, CH, AU, NZ, CA, NO, SE |
| Asia | SGD, THB, CNH, CNY, HKD, IDR, INR, KRW, MYR, PHP, TWD, VND | SG, TH, CN, HK, ID, IN, KR, MY, PH, TW, VN |
| Other | DKK, ILS, MXN, ZAR | DK, IL, MX, ZA |
| Swap-only | AED, ARS, BDT, BRL, CLP, COP, CZK, EGP, HUF, KZT, LKR, NGN, PLN, PEN, RON, SAR, TRY | AE, AR, BD, BR, CL, CO, CZ, EG, HU, KZ, LK, NG, PL, PE, RO, SA, TR |
