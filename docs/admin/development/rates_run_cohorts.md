# `rates/run_cohorts.py` — Region-Aware Cohort Routing

- **Date**: 2026-05-13
- **Module**: [`src/imdr/domains/rates/run_cohorts.py`](../../../src/imdr/domains/rates/run_cohorts.py)
- **Consumers**: [`scripts/rates/citi/rates_citi_live.py`](../../../scripts/rates/citi/rates_citi_live.py), [`scripts/rates/citi/rates_citi_live_hourly.py`](../../../scripts/rates/citi/rates_citi_live_hourly.py)
- **Tests**: `tests/unit/test_run_cohorts.py`
- **Related**: [country_anchor_restructure_progress.md](country_anchor_restructure_progress.md), [last_business_day_call_sites.md](last_business_day_call_sites.md)

---

## Why it exists

The rates universe spans curves from three regions whose data settles at very different UTC times. A single US-anchored daily run after NY close means Asia curves wait ~12 hours after they settle in Citi before they land in IMDR. `run_cohorts` slices the universe into **ASIA / EUROPE / AMERICAS** cohorts so each region's curves are pulled shortly after that region's market actually closes.

The schedule is driven from `imdr_hourly.py` / `imdr_daily.py`. Each cron fire calls the same script with `--region auto`; the module decides which cohort to actually run based on the current UTC hour.

---

## The five public functions

| Function | Purpose | Used by |
|---|---|---|
| `select_curves(curves, region)` | Filter `CurveEntry` list to the cohort | live + hourly scripts (line `live:187`, `hourly:343`) |
| `target_for_region(region)` | Region-anchored `last_business_day` UTC datetime | live script (line `live:160`) |
| `resolve_region_auto(now_utc=None)` | UTC-hour → region (or `None` if outside any window) | live + hourly scripts |
| `default_run_label(region)` | Stable label `"ASIA_PM"` / `"EUROPE_PM"` / `"AMERICAS_PM"` for RunReport, email subject, log filename | live + hourly scripts |
| `is_static_quote_fire(region, now_utc=None)` | True on the *last* hourly fire of the region's window — gate for pulling derived/static quotes (bfly, ssw, rc) once per day instead of every fire | live script only (line `live:179`) |

---

## The four data tables (single source of truth)

### `LATE_PUBLISH_CURVES` — overnight publishers

```python
frozenset({
    ("USD", "SOFR"),       # NY Fed T+1 ~12:00 UTC
    ("USD", "FEDFUND"),    # NY Fed H.15 T+1 ~13:00 UTC
    ("CAD", "CORRA"),      # BoC T+1 ~13:00 UTC
    ("JPY", "TONAR_JSCC"), # JSCC CCP mark, post-Asia EOD
    ("JPY", "TONAR_LCH"),  # LCH CCP mark, post-London EOD
})
```

These are forced into AMERICAS regardless of underlying currency. Note `JPY/TONAR_*`: even though JPY is an Asian currency, the CCP marks aren't published until after the relevant EOD batch, so pulling them in the Asia window would miss the data. The CCP-cleared TONAR variants ride with AMERICAS while plain TONAR stays in the ASIA cohort by currency.

### `REGION_MARKETS` — currency-home-market → region

```python
{
  "asia":     {"AU","NZ","JP","HK","SG","TH","CN","ID","IN","KR","MY","PH","TW","VN"},
  "europe":   {"EU","UK","CH","NO","SE","DK"},
  "americas": {"US","CA","MX"},
}
```

Routing: each `CurveEntry` looks up `countries_for_currency(c.ccy)` (alphabetical, first-only — every ccy maps 1:1 today) and matches the resulting country_code against these sets.

### `REGION_ANCHORS` — latest-closing market per region for `last_business_day(...)`

```python
{"asia": "JP", "europe": "UK", "americas": "US"}
```

Picks the latest-closing country in each cohort so the "target date" reflects when the cohort's data has actually settled. JP closes after AU/SG/HK; UK closes after continental EU; US closes after CA/MX.

### `UTC_FIRE_WINDOWS` — half-open `[start, end)` UTC hour windows

```python
{
  "asia":     (8,  15),   # 08-15 UTC = 16:00-23:00 SGT — after Asia equity close
  "europe":   (16, 21),   # 16-21 UTC = 17:00-22:00 BST — after London close
  "americas": (21,  6),   # 21-06 UTC, wraps midnight — after NY close + Citi publish
}
```

`_hour_in_window` handles the americas wrap by `hour >= 21 OR hour < 6`. Windows don't overlap. Gaps (hours 6, 7, 15) return `None` from `resolve_region_auto` → scheduled fire is a no-op.

### `STATIC_QUOTE_FIRE_HOURS` — once-per-day "pull derived quotes" slot per region

```python
{"asia": 12, "europe": 18, "americas": 3}
```

Under the 0/3/6/.../21 UTC hourly cron, each region's window has multiple fires; only the **last** fire pulls the derived/static quote set (`bfly`, `ssw`, `rc` — don't move intraday). Saves ~5 redundant tag-calls per day per region, no data loss. Comment in source documents the arithmetic:

- asia: window 08-15 → fires at 09 + 12 → last = **12**
- europe: window 16-21 → fires at 18 → only = **18**
- americas: window 21-06 → fires at 21, 00, 03 → last before 06 = **3**

---

## Routing algorithm (`select_curves`)

```
for curve in active_curves:                    # ceased curves always excluded
    if (curve.ccy, curve.curve) in LATE_PUBLISH_CURVES:
        if region == "americas": include
        else: skip                              # SOFR/FEDFUND never go to ASIA/EUROPE
    else:
        country = countries_for_currency(curve.ccy)[0]
        if country in REGION_MARKETS[region]: include
```

`region == "all"` short-circuits — returns every active curve (used for full backfills and `--region all` invocations).

Ceased curves are filtered up front so historical-only curves are never re-queried in scheduled runs. Curves with an unrecognized currency (no `countries_for_currency` match) are silently dropped — guard rather than explode.

---

## Call flow at runtime

```
cron fires hourly/daily at H UTC
   ↓
python -m scripts.rates.citi.rates_citi_live --region auto
   ↓
region = resolve_region_auto()           # H → "asia" | "europe" | "americas" | None
   ↓ (if None: log skip, exit 0)
target  = target_for_region(region)      # last_business_day at region's anchor
cohort  = select_curves(universe, region)# filter to region's curves
label   = default_run_label(region)      # "ASIA_PM" etc.
   ↓
[live-only] is_static_quote_fire(region) decides whether to include bfly/ssw/rc
   ↓
RatesPipeline runs on `cohort` for `target` → DB + email
```

---

## Known issues / divergences

### 1. `target_for_region` uses the legacy `segment="RATES"` form

```python
return last_business_day(anchor, segment="RATES")
```

This is the **legacy keyword form** of `last_business_day` and emits `DeprecationWarning` per Phase D Step 2. The modern signature is `last_business_day(country_code, calendar_code)`. Step 7 migration should rewrite this to look up the rates calendar per country — likely `GT` (SIFMA US Govt Bond) for `US`, `LS` (London) or `TE` (TARGET2) for `UK`, `TK` for `JP` — and pass it explicitly. The bridge currently resolves `(US, RATES) → GT` via `dim_market_calendar.is_default=1`, so behaviour is correct **today** but brittle to bridge edits. See [last_business_day_call_sites.md](last_business_day_call_sites.md).

### 2. `REGION_MARKETS` is hardcoded in the module

The country-code → region mapping is duplicated here rather than read from `dim_country` or `countries.yml`. If a new country is added to the rates universe (e.g. ZAR/South Africa, BRL/Brazil), it must be added to this table manually or its curves will silently route to no cohort. Worth migrating to a `dim_country.region` column after Phase D Step 5–6 lands.

### 3. `REGION_ANCHORS` couples the cohort calendar to a single country

Picking `JP` as the Asia anchor means an Asia-cohort run on a JP-only holiday (e.g. Golden Week) anchors `target` to the previous JP trading day even though AU/SG/HK are open. Acceptable trade-off as long as the down-cohort consumer treats `target.date()` as the publish reference rather than per-curve close.

### 4. `is_static_quote_fire` arithmetic baked into a dict comment

The dict `{"asia": 12, "europe": 18, "americas": 3}` is derived from the intersection of `UTC_FIRE_WINDOWS` with the cron schedule `0/3/6/.../21`. If either the windows or the cron change, this needs to be hand-recomputed. Consider deriving it programmatically (`max(h for h in CRON_HOURS if _hour_in_window(h, window))` with wrap handling) so the three tables stay self-consistent.

### 5. Currency → country uses alphabetical-first

`countries_for_currency(c.ccy)` picks the first country alphabetically when multiple exist. Today every ccy maps 1:1 (CNH/CNY/CNO all `CN`, etc.) so this is fine, but the comment in `select_curves` flags it as a soft invariant. EUR is the obvious watch-point — `countries_for_currency("EUR")` should return `["EU"]` (the pseudo-country), not a member-state list.

---

## When to touch this module

- **Adding a curve to a new currency**: confirm `countries_for_currency(ccy)` returns the expected country and that country is in the right `REGION_MARKETS` set.
- **A vendor changes a publish window**: update `LATE_PUBLISH_CURVES` if the curve moves out of (or into) the overnight-publisher bucket.
- **Cron schedule changes**: re-derive `STATIC_QUOTE_FIRE_HOURS` (see issue 4).
- **Region calendar disagreement** (e.g. SIFMA vs NYSE on Veterans Day): update `target_for_region`'s `calendar_code` once Step 7 migrates off `segment="RATES"`.
