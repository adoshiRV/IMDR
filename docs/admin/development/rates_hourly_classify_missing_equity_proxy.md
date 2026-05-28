# Tech Debt — Rates hourly "why missing?" classifier uses equity-exchange hours as proxy

- **Date filed**: 2026-05-13
- **Status**: open (deferred — not in country-anchor restructure scope)
- **Triggered by**: review of Step 6 (`countries_for_currency` ordering). Surfaced by an observation that calling the `[0]` country's *equity exchange status* "the ccy's market state" is a category error for rates.
- **Owner**: rates ingest
- **Severity**: 🟡 misleading email/report status labels; **no data correctness impact**

## TL;DR

[`scripts/rates/citi/rates_citi_live_hourly.py`](../../../scripts/rates/citi/rates_citi_live_hourly.py) labels missing-data gaps with **equity exchange semantics** (`pre_open` / `open` / `post_close`). The script ingests **rates** data (RFRs, IBOR/NDIRS, OIS curves) — none of which trade on an exchange. The classifier is using the wrong clock as a proxy for "should this hour have data?" Reports today contain misleading reasons ("market not yet open" for EUROSTR at 04:00 UTC); ingest itself is unaffected.

## Where the mismatch lives

[`scripts/rates/citi/rates_citi_live_hourly.py:_classify_missing`](../../../scripts/rates/citi/rates_citi_live_hourly.py):

```python
def _classify_missing(ccy: str, utc_dt: datetime) -> tuple[str, str]:
    countries = countries_for_currency(ccy)
    if not countries:
        return "", "unknown"
    mkt = countries[0]
    if ccy.upper() in _OTC_RFR_CCYS:           # only {"USD", "CAD"}
        # 24h OTC carve-out for these two ccys
        ...
        return mkt, "otc"
    return mkt, _market_status(mkt, utc_dt)    # equity-hours path
```

And `_market_status`:

```python
def _market_status(market_code: str, utc_dt: datetime) -> str:
    country = get_country(market_code)
    tz = ZoneInfo(country.timezone)
    local_dt = utc_dt.astimezone(tz)

    if not is_trading_day(market_code, local_dt.date()):
        return "non_trading"

    th = country.trading_hours        # ← countries.yml equity hours (NYSE 09:30-16:00, …)
    if th is None:
        return "otc"

    if is_market_open(market_code, utc_dt):   # ← compares to equity exchange clock
        return "open"
    ...
```

`countries.yml.trading_hours` models **equity exchange** windows:

```yaml
US:
  trading_hours: { open: "09:30", close: "16:00" }    # NYSE / NASDAQ
JP:
  trading_hours: { open: "09:00", close: "15:30" }    # TSE
```

Rates products don't trade on those exchanges.

## Why this is wrong for rates

| Rates product class | Actual cadence | Why equity hours don't apply |
|---|---|---|
| RFRs (SOFR, EUROSTR, SONIA, TONAR, SARON, AONIA, CORRA, NZIONA, NOWA, STINA) | Once-daily fix by administrator (Fed, ECB, BoE, BoJ, SNB, RBA, BoC, RBNZ, NB, RB) | The fixing time has no relation to exchange open/close. SOFR publishes ~12:00 UTC; EUROSTR ~07:00 UTC; SONIA ~07:00 UTC. None of these track NYSE/LSE/TSE clocks. |
| APAC IBOR / NDIRS (HIBOR, KLIBOR, SHIBOR, TAIBOR, CNH HIBOR) | Once-daily mid-morning local fix (e.g., HIBOR 11:15 HKT, KLIBOR 11:00 MYT) | Published before lunch on the local trading day; the equity exchange is concurrently open, so the proxy "happens to work" — but only by coincidence. |
| OIS / IRS / basis swaps (live, intraday) | OTC dealer market; effectively 24×5 on trading days | No central exchange clock. Liquidity is bank-hour weighted but data flows continuously. |
| Government bonds (cash) | Primarily OTC; some exchange listings, but pricing is OTC | Exchange listings exist but aren't the source. |

The whole `DEFAULT_CURVES` list (18 curves: 12 RFRs + 6 APAC IBOR/NDIRS) falls into the first two rows. **None of them is an equity exchange instrument.**

## Why a partial fix is already there

The author noticed the mismatch and inserted a carve-out for the two most obvious cases:

```python
# Currencies whose RFR publishes from ~00:00 UTC via overnight trading rather
# than on the local equity-market clock (see module docstring). Treated as
# OTC for classification so early-UTC hours don't falsely show "pre_open".
_OTC_RFR_CCYS = {"USD", "CAD"}
```

But the same logic applies to **every** other RFR/IBOR in the universe. The carve-out should either be the whole universe or be replaced with a different model. The partial-coverage state is what makes the bug subtle: it half-works for USD/CAD and silently mislabels everything else.

## Practical effect today

The ingest email's "missing reasons" block shows labels like:

- `EUR EUROSTR: missing — Market not yet open` at 04:00 UTC
- `JPY TONAR: missing — Market closed — data missing` at 12:00 UTC (TSE closes 06:00 UTC; TONAR was already published at ~01:00 UTC)
- `GBP SONIA: missing — Market not yet open` at 06:00 UTC (LSE 07:00 UTC; SONIA fixed at ~07:00 UTC, so the equity proxy *happens* to align here)
- `AUD AONIA: missing — Market closed — data missing` after Sydney equity close, even though AONIA continues to publish on its own clock

The "_STATUS_REASON" dict at the call site:

```python
_STATUS_REASON = {
    "non_trading": "Market holiday/weekend",       # ← correct for rates
    "pre_open":    "Market not yet open",          # ← misleading for rates
    "open":        "Market open — data pending or gap",  # ← misleading
    "post_close":  "Market closed — data missing",       # ← misleading
    "otc":         "24h OTC market — data missing",      # ← correct (only fires for USD/CAD)
    "unknown":     "No market mapped",
}
```

Ingest itself proceeds correctly: data lands when Citi serves it. The misleading status doesn't gate any decision — it's purely a human-readable label.

## Recommended fix

The classifier only needs to distinguish **"intentionally empty"** from **"anomalously empty"** — that's all the email report consumer cares about. The hourly runner already pulls the full 00:00 → 23:59 UTC window every fire and MERGEs idempotently (see module docstring on "Window strategy"), so the script doesn't need to *predict* when each curve's data will appear. Eventually-consistent ingest doesn't need fine-grained intra-day status.

Two states are enough:

| State | Meaning | Action |
|---|---|---|
| `non_trading` | Weekend or holiday on the curve's rates calendar | Expected empty — no alert |
| `missing` | Trading day, no data yet on Citi | Genuine gap — flag in email |

That collapses `_classify_missing` to a one-liner once Step 7 wires every curve to `(country_code, calendar_code)`:

```python
def _classify_missing(country_code: str, calendar_code: str, d: date) -> str:
    return "non_trading" if not is_trading_day(country_code, calendar_code, d) else "missing"
```

### What gets deleted

- `_market_status` function (whole equity-hours classifier)
- `_OTC_RFR_CCYS = {"USD", "CAD"}` carve-out (no longer needed; the new model subsumes it)
- `_STATUS_REASON` entries for `pre_open`, `open`, `post_close`, `otc`, `unknown` (only `non_trading` + `missing` survive)
- The `import is_market_open` line (no longer used)

### What we need

Per-curve `(country_code, calendar_code)` for the 18 hourly-runner curves. This is the **same metadata Step 7 is going to produce anyway** to migrate the holiday calls off `segment="RATES"`. The fix below is a natural follow-on of Step 7, not a separate project.

A sketch of the per-curve mapping (final values during Step 7):

| ccy | country | calendar | notes |
|---|---|---|---|
| USD | US | GT | SIFMA US Govt Bond |
| EUR | EU | TE | TARGET2 |
| GBP | UK | LS | LSE / Bank of England |
| JPY | JP | (JP rates calendar) | TBD during Step 7 |
| CHF | CH | (CH rates calendar) | TBD |
| AUD | AU | (AU rates calendar) | TBD |
| CAD | CA | (CA rates calendar) | TBD |
| NZD | NZ | (NZ rates calendar) | TBD |
| NOK | NO | (NO rates calendar) | TBD |
| SEK | SE | (SE rates calendar) | TBD |
| SGD | SG | (SG rates calendar) | TBD |
| THB | TH | (TH rates calendar) | TBD |
| HKD | HK | (HK rates calendar) | TBD |
| CNH | CN | (CN rates calendar) | offshore CNY |
| CNY | CN | (CN rates calendar) | onshore |
| MYR | MY | (MY rates calendar) | NDIRS |
| TWD | TW | (TW rates calendar) | NDIRS |

(The "TBD" rows resolve themselves when Step 7's grep enumerates every legacy `segment="RATES"` call site and decides the calendar_code for each.)

### Why this is simpler than the earlier "publish profile" sketch

An earlier version of this doc proposed adding per-curve `publish_time_utc` metadata and a 4-state classifier (`pre_publish` / `missing_after_publish` / `published_continuously` / `non_trading`). That was unnecessary:

- The script doesn't gate on publish time — it always pulls the full UTC day and MERGEs.
- The email's job is to flag anomalies for ops, not to give a minute-precise SLA prediction.
- "Trading day with missing data" is already the right alert. If a publisher is consistently late, that's a publisher problem, not something the ingest classifier should hide.

The two-state model captures everything the report consumer actually uses.

## Why this isn't being fixed inside Step 7 itself

- **Phase D Step 7 scope is mechanical**: rewrite `is_holiday(market_code, d, segment="RATES")` → `is_holiday(country_code, "GT", date)` at ~16 consumer call sites. Adding a semantic rewrite (`_classify_missing` replacement) to that PR muddies the diff and complicates bisects.
- **Not data-correctness blocking**: ingest writes the right rows; only the email's "why missing" prose is wrong, so it's safe to defer.
- **Needs Step 7's `(country_code, calendar_code)` mapping anyway**: the fix is mostly free *after* Step 7 — once every curve knows its rates calendar, `_classify_missing` collapses to a single `is_trading_day` call.

## Suggested sequencing

1. **Phase D Step 7 lands first** — produces the per-curve `(country_code, calendar_code)` mapping as a side effect of migrating the holiday calls.
2. **Follow-on PR** (small, ~30 lines): rewrite `_classify_missing` to the 2-state model, delete `_market_status` + `_OTC_RFR_CCYS` + the unused `is_market_open` import, prune `_STATUS_REASON`.
3. **Grep symmetric uses elsewhere**: check the fx / equity / commodity hourly + live runners for the same equity-hours-as-rates-proxy pattern. Equity and fx may be using exchange hours *correctly* (since their underlying data does flow on exchange clocks for some products); a quick audit confirms which scripts inherit the bug.

## Cross-references

- Country-anchor restructure: [country_anchor_restructure_progress.md](country_anchor_restructure_progress.md) (Step 6 review surfaced this finding)
- Modern calendar API: see "Recommended call form" in [calendar_module.md](../calendar_module.md)
- The misleading docstring polish in Step 6 that prompted the finding: [run_cohorts.py:14-18](../../../src/imdr/domains/rates/run_cohorts.py) and [rates_citi_live_hourly.py:_classify_missing](../../../scripts/rates/citi/rates_citi_live_hourly.py)
