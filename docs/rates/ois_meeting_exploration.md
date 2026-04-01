# OIS Meeting — Meeting-Dated OIS Exploration

Market-implied central bank policy rate paths from Citi Velocity.

- **Explored**: 2026-03-26
- **Source**: `RATES.OIS_MEETING.{CCY}.{YEAR}.{MEETING_DATE}`
- **Total tags**: 449
- **Proposed table**: `macro.fact_cb_meeting_ois` (NOT `calendar.fact_imm_dates` — see rationale below)
- **DO NOT re-run** — all results documented here

---

## What Is This Data?

Each tag gives a **daily time series of the OIS rate implied through a specific central bank meeting**. This is not a forecast or opinion — it is the **observable swap market price** for overnight rates cumulated to each meeting date.

The difference between consecutive meetings gives the **implied probability of a rate change** at that meeting:

```
JPY Mar 19: 0.730%  (current policy rate, ~0.50% target)
JPY Apr 28: 0.884%  → +15bp = ~60% probability of a 25bp BOJ hike
JPY Oct 30: 1.142%  → ~40bp cumulative = 2 hikes priced by year-end
```

---

## Why NOT `fact_imm_dates`

The blueprint groups IMM dates and meeting-dated OIS together. They should be **separate tables**:

| | IMM Dates | Meeting-Dated OIS |
|---|---|---|
| **What** | Standardised quarterly expiry dates (3rd Wed of Mar/Jun/Sep/Dec) | CB-specific meeting dates (irregular, 6-8/year per CB) |
| **Nature** | Mechanical calendar dates for futures/swap settlement | Market-implied pricing of CB policy decisions |
| **Source** | Algorithmic (`src/imdr/market_calendar/imm.py`) | Citi Velocity (`RATES.OIS_MEETING`) |
| **Purpose** | Futures rolls, swap settlement, FRA fixing | CB hike/cut probability, front-end RV, policy path |
| **Update** | Static per year | Daily time series (price changes every day) |
| **Grain** | One row per date | One row per (date × meeting × observation_date) |

Mixing them creates a table with confused semantics, nulls, and no clean join key. Instead:

- **`calendar.fact_imm_dates`** — IMM quarterly dates, futures roll calendar (static/algorithmic)
- **`calendar.fact_cb_meeting_ois`** — market-implied CB rate per meeting (daily time series from Citi)

`fact_cb_meeting_ois` joins naturally to `calendar.cb_events` via meeting date + CB name.

---

## Tag Format

`RATES.OIS_MEETING.{CCY}.{YEAR}.{YYYYMMDD}`

Meeting dates must match the actual CB calendar — incorrect dates return no data.

---

## Currencies & 2026 Meeting Dates

All 10 G10 currencies confirmed. **All return data for future/recent meetings.**

| Currency | Central Bank | 2026 Meetings | Latest Implied Terminal |
|---|---|---|---|
| **USD** | Fed (FOMC) | Jan 28, Mar 18, Apr 29, Jun 17, Jul 29, Sep 16, Oct 28, Dec 09 | Dec: 3.69% (flat, no cuts) |
| **JPY** | BOJ | Jan 23, Mar 19, Apr 28, Jun 16, Jul 31, Sep 18, Oct 30 | Oct: 1.14% (~40bp hikes) |
| **AUD** | RBA | Feb 04, Mar 18, May 06, Jun 17, Aug 12, Sep 30, Nov 04 | Aug: 4.49% (~38bp tightening) |
| **EUR** | ECB | Feb 05, Mar 19, Apr 30, Jun 11, Jul 23, Sep 10, Oct 29 | Jul: 2.45% (~30bp cuts) |
| **GBP** | BoE (MPC) | Feb 05, Mar 19, Apr 30, Jun 18, Jul 30, Sep 17, Nov 05 | Nov: 4.34% (~60bp cuts) |
| **NZD** | RBNZ | Feb 19, Apr 09, May 28, Jul 08, Sep 02, Oct 28, Dec 09 | Jul: 2.46% (easing) |
| **CAD** | BoC | Jan 28, Mar 18, Apr 29, Jun 10, Jul 15, Sep 02, Oct 28 | browse confirmed |
| **CHF** | SNB | Mar 19, Jun 18, Sep 24, Oct 12, Dec 10 | browse confirmed |
| **NOK** | Norges Bank | Jan 22, Mar 26, May 07, Jun 18, Aug 13, Sep 24, Nov 05 | browse confirmed |
| **SEK** | Riksbank | Jan 29, Mar 19, May 07, Jun 17, Aug 20, Sep 24, Nov 04 | browse confirmed |

Historical data available back to **2020** for most currencies.

---

## Sample Data

### USD (Fed) — Implied Rate Path (as of 2026-03-25)

| Meeting | Implied Rate | Δ vs Prior | Interpretation |
|---|---|---|---|
| Mar 18 | 3.648% | — | Hold (current ~3.75% target) |
| Apr 29 | 3.666% | +1.8bp | Hold |
| Jun 17 | 3.682% | +1.6bp | Hold |
| Jul 29 | 3.685% | +0.3bp | Hold |
| Sep 16 | 3.705% | +2.0bp | Hold |
| Oct 28 | 3.712% | +0.7bp | Hold |
| Dec 09 | 3.690% | -2.2bp | Slight easing priced |

Market pricing: essentially **no Fed cuts in 2026**.

### JPY (BOJ) — Implied Rate Path (as of 2026-03-25)

| Meeting | Implied Rate | Δ vs Prior | Interpretation |
|---|---|---|---|
| Mar 19 | 0.730% | — | Post-meeting (hiked to 0.50%) |
| Apr 28 | 0.884% | +15.3bp | ~60% chance of 25bp hike |
| Jun 16 | 0.948% | +6.5bp | Gradual normalization |
| Jul 31 | 1.007% | +5.8bp | Through 1.00% |
| Sep 18 | 1.067% | +6.1bp | |
| Oct 30 | 1.142% | +7.4bp | ~40bp of total hikes |

Market pricing: **BOJ hiking to ~1.14% by Oct** (current: 0.50%).

### AUD (RBA) — Implied Rate Path (as of 2026-03-25)

| Meeting | Implied Rate | Δ vs Prior | Interpretation |
|---|---|---|---|
| Mar 18 | 4.106% | — | Current (just cut to 4.10%) |
| May 06 | 4.254% | +14.8bp | Partial tightening |
| Jun 17 | 4.322% | +6.7bp | |
| Aug 12 | 4.487% | +16.6bp | +38bp total |

### Raw Daily Time Series (USD Jun 17 FOMC)

Shows how the market repriced the Jun FOMC meeting day-by-day:

```
2026-02-24  3.508%   ← start of period
2026-02-27  3.502%
2026-03-06  3.504%   ← post-NFP
2026-03-12  3.586%   ← CPI surprise repricing (+8bp in 2 days)
2026-03-18  3.608%   ← FOMC day
2026-03-19  3.662%   ← post-FOMC hawkish repricing (+5bp)
2026-03-25  3.682%   ← latest
```

Total repricing: +17bp in one month as the market shifted from pricing one cut to no cuts.

---

## Pipeline Considerations

- **Proposed table**: `macro.fact_cb_meeting_ois`
- **Tags per day**: 10 ccys × ~7 meetings avg = ~70 tags
- **Historical depth**: Back to 2020 (6 years)
- **Update**: Daily (each tag is a time series that updates with each business day)
- **Meeting dates**: Must be dynamically fetched via `tagbrowsing` each year, or maintained in calendar config. Incorrect dates return no data.
- **Key derived metric**: Δ between consecutive meetings = implied bp of hike/cut = implied probability at 25bp granularity
- **Join**: Links to `calendar.cb_events` via meeting date + currency. Lives in `macro` (not `calendar`) because it's market pricing of CB policy, not the event itself.
