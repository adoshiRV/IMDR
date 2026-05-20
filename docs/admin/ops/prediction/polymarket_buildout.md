# Polymarket Prediction-Market Integration — Buildout Notes

_Last updated: 2026-04-29_

## Why we're doing this

Polymarket is the deepest public prediction-market venue. For a macro desk that already runs rates / FX / commodities feeds in IMDR, it adds something no traded instrument prices: **crowd-sourced probability for events that move markets but don't have a liquid hedge** — Fed paths, geopolitical binaries (Iran / Russia / Taiwan), inflation strikes, recession bets, election outcomes.

The intent is to bring Polymarket into IMDR alongside the other domains so the desk can:

1. Compare crowd-sourced probabilities against dealer-implied probabilities (OIS, Fed funds, FX vol surfaces).
2. Track non-traded events (geopolitics, regulatory) where Polymarket is the only quote.
3. See how news flow re-prices opinion vs traditional markets.

Build is incremental. Each step is small, validated, and preserves option value for the next.

## Gameplan arc

| Step | Goal | Status |
|------|------|--------|
| 1 | First-touch exploration of Gamma API, WebSocket shape, update cadence | done |
| 2 (orig) | Scheduled event snapshots (2x/day) + analytic companion | superseded — kept on disk |
| **2 (current)** | **URL-driven watcher: SQLite on `C:\IMDR_LOCAL\polymarket\` with poll / loop / cleanup** | **done** |
| **3** | **Polywatch — move-detection runtime over `observations.db` with email alerts** | **done** |
| 3.5 | Macro snapshot — Teams channel posts (Adaptive Cards via Workflows webhook) | **done — AM via `imdr_daily.py`, PM via `imdr_evening.py`. See [teams_integration.md](teams_integration.md). Polywatch SPIKE/MODAL_FLIP alerts on the same channel still deferred.** |
| 4 | Cross-asset overlay — align event panel against IMDR rates/FX snapshots | later |
| 5 | Consumption surface — morning brief, alert thresholds, Slack/email | later |
| 6 | Historical backfill via CLOB `/prices-history` for retrospective study | later |
| 7 | Promote `C:\IMDR_LOCAL\` SQLite into the IMDR `prediction` MSSQL schema (only if cross-team access needed) | later |

## What Polymarket actually exposes

Public, no-auth APIs:

- **Gamma** (`https://gamma-api.polymarket.com`) — markets, events, tags. The catalog and current state.
- **CLOB** (`https://clob.polymarket.com`) — orderbook, prices, **historical price series**. Readable anonymously; auth only required for trading.
- **WebSocket market channel** (`wss://ws-subscriptions-clob.polymarket.com/ws/market`) — push events on subscribed token IDs (`book`, `price_change`, `last_trade_price`).
- **Data API** — user positions / activity. Not relevant for read-only monitoring.

Rate limits are generous: Gamma `/markets` 300 req/10s, `/events` 500 req/10s. Never the constraint.

### Data model

- An **event** is a question or topic — e.g. "Fed March 2026 FOMC decision".
- An event groups one or more **markets**. A market is always a binary YES / NO question — e.g. "No change at March 2026 FOMC".
- Each market has two **CLOB tokens** (ERC1155 on Polygon): `clobTokenIds = [YES_token, NO_token]`. The `outcomePrices` field on the market gives `["yes", "no"]` (stringified JSON, two outcomes summing to ~1 within a single market).
- Multi-market events represent **mutually-exclusive outcomes**. YES probabilities across the markets in such an event approximate a probability distribution and should sum to ≈ 1.
- `event_id` and `condition_id` are the stable keys (`condition_id` for markets, `event_id` for events).

### Update cadence (observed)

- Gamma `/markets` `updatedAt` field bumps when any state changes (price, volume, etc.).
- Trades arrive sparse: ~78 trades / 2 min across 165 macro markets during US hours; near-zero during Asia overnight.
- Orderbook flutter is heavy: ~46k `price_change` events / 2 min. ~99% are MM quotes adjusting depth without moving top of book — must be filtered for any consumer.

## What we built so far

### Step 1 — first-touch exploration

[scripts/explore/explore_polymarket_gamma.py](../../scripts/explore/explore_polymarket_gamma.py)
Run-once probe. Hit `/markets` and `/events`, count fields, sample contracts, time the update cadence by polling 5 markets every 10s for 60s. Cached results to `data/cache/polymarket/{markets,events}_sample.json`, `macro_hits.json`, `frequency_probe.json`. **Don't re-run.**

[scripts/explore/polymarket_macro_stream.py](../../scripts/explore/polymarket_macro_stream.py)
Live WebSocket tape with macro filtering. Phase 1 builds the watchlist by querying Gamma `/tags` and filtering tag labels/slugs against a macro regex (Fed / FOMC / inflation / oil / China / Russia / Iran / recession / election / geopolitics …) plus an exclude regex (sports / entertainment). Phase 2 connects the WS, subscribes to the YES tokens, parses the three event types, and prints filtered output.

Used in development to prove the data flow. **Not the production path** given the desk wants 2x/day cadence — keeps it as a dev artefact and a source of reusable helpers (`MACRO_RE`, `EXCLUDE_RE`, `fetch_macro_tags`, `fetch_events_for_tag`, `_parse_json_field`, `_to_float`, `_volume`).

Outputs:

- `data/cache/polymarket/watchlist.json`
- `data/cache/polymarket/stream.jsonl`

### Step 2 — scheduled snapshots + analytic companion

The production path. Aligned with the rest of IMDR (every domain runs on scheduled HTTP polls, not streams).

#### 2A. Snapshot job

[scripts/explore/polymarket_event_snapshot.py](../../scripts/explore/polymarket_event_snapshot.py)
Single HTTP-only run, ~7 sec wall time. Walks the same macro-tag filter as Step 1's watchlist build but **keeps the event grouping** (events are the unit; markets are nested children). Per event computes derived metrics: `modal_question` / `modal_yes` / `runner_up` / `implied_prob_sum` / `hhi` / `illiquid_flag` (spread > 20pp on modal market). Writes one JSONL line per event.

**Default schedule** (editable at the top of the file): 12:00 UTC and 20:00 UTC (08:00 ET / 16:00 ET — straddles the US macro session).

**Output layout:**

```
data/cache/polymarket/snapshots/
└── 2026-04-24/
    ├── snapshot_2057Z.jsonl    ← one event per line
    ├── snapshot_2102Z.jsonl
    └── manifest.json           ← index of snapshots that landed today
```

**JSONL record schema** (one line per event):

```json
{
  "snapshot_ts": "2026-04-24T20:57:54.732+00:00",
  "snapshot_label": "PM",
  "event_id": 192034,
  "slug": "fed-march-2026-decision",
  "title": "Fed March 2026 FOMC decision",
  "theme": "interest rates",
  "end_date": "2026-03-19T18:00:00Z",
  "total_volume": 1353468,
  "total_liquidity": 234000,
  "event_volume_24h": 4500,
  "market_count": 18,
  "markets": [
    {
      "condition_id": "0xabc...",
      "question": "Will the Fed's lower bound reach 3.25% before 2027?",
      "outcomes": ["Yes", "No"],
      "yes_token": "...", "no_token": "...",
      "yes": 0.665, "no": 0.335,
      "best_bid": 0.66, "best_ask": 0.67, "spread": 0.01,
      "last_trade_price": 0.665,
      "volume": 250000, "volume_24h": 1200, "liquidity": 8000,
      "updated_at": "2026-04-24T20:55:11Z",
      "end_date": "2027-01-01T00:00:00Z",
      "closed": false
    }
  ],
  "derived": {
    "modal_question": "Will the Fed's lower bound reach 3.25% before 2027?",
    "modal_yes": 0.665,
    "runner_up_question": "Will the Fed's lower bound reach 3.0% before 2027?",
    "runner_up_yes": 0.230,
    "implied_prob_sum": 0.989,
    "hhi": 0.522,
    "illiquid_flag": false
  }
}
```

#### 2B. Analytic companion

[scripts/explore/polymarket_event_analytics.py](../../scripts/explore/polymarket_event_analytics.py)
Offline analytic. Reads every `snapshot_*Z.jsonl` under `data/cache/polymarket/snapshots/`, groups by `event_id`, emits three markdown reports under `data/cache/polymarket/analytics/`.

**(b) Move classification** — `move_classification_{YYYY-MM-DD}.md`

Per-event consecutive-snapshot deltas, classified by `|Δ modal_yes|`:

| Class | Threshold |
|------|-----------|
| BIG_MOVE | ≥ 10pp **OR** modal-outcome identity changed |
| MOVE | 5–10pp |
| DRIFT | 1–5pp |
| FLAT | < 1pp |
| ILLIQUID | spread > 20pp on modal market in either snapshot |
| NEW | event first appears mid-panel |
| RESOLVED | event drops out before end of panel |

Grouped by theme; sorted within theme by BIG_MOVE count, then MOVE count, then max |Δ|, then volume.

**(c) Theme rollup** — `theme_rollup_{YYYY-MM-DD}.md`

Per snapshot, per theme:

- Event count
- Aggregate volume
- Mean / median modal_yes across events
- Activity score: `Σ|Δ modal_yes|` since previous snapshot. Does **not** respect the ILLIQUID flag — answers "how much did the theme move?" rather than "how much was tradeable?". The two reports answer different questions intentionally.
- Hottest event (largest absolute delta) with its signed delta.

**(a) Event statistics** — `event_stats.md`

Per event over the full panel history. Requires ≥ 7 observations to compute meaningfully; sub-7 events are flagged `insufficient_data`.

- `realised_vol` — population stddev of successive Δ modal_yes
- `ac1`, `ac2` — autocorrelation of modal_yes at lag 1, 2
- `modal_dwell` — number of trailing consecutive snapshots whose modal outcome matched the latest
- `am_pm_range_p90` — p90 of `|PM_modal − AM_modal|` across calendar dates that have both AM and PM snapshots

---

### Step 2 (current) — URL-driven watcher with SQLite on `C:\IMDR_LOCAL\`

The 2x/day flow above produced one valuable insight (events overlap and need event-level grouping) and one wrong assumption (that 12-hour cadence was the right rhythm). The desk wanted faster polling, hand-curated watchlists, and explicitly **not** another table inside the IMDR MSSQL database. We pivoted on 2026-04-27.

#### Why the pivot

- **Cadence too slow.** A 12-hour gap can miss the entire shape of a tape-bomb-driven move. The desk asked for "60s / 5m / 10m / 30m" cadences — minutes-not-hours.
- **Watchlist by tag was too broad.** A tag-based regex pulled 42 events totalling $7.3M volume; six hand-picked Polymarket category slugs (Fed, Fed Chair, Iran, Strait of Hormuz, Ukraine, Trump) cover ~$740M in macro-relevant volume — ~100× richer in the contracts that actually move markets.
- **Storage doesn't belong in IMDR.** The user's verbatim instruction: *"we don't need to make a whole table on IMDR for this — some fast polling solutions like this can be put onto SQLite on my C drive ... main thing is monitoring efficiently."* `C:\IMDR_LOCAL\` was designated as the host for fast-polling local utilities; each utility gets its own subdirectory.

#### Where the data lives

```
C:\IMDR_LOCAL\
└── polymarket\                              ← outside IMDR DB and repo
    ├── watchlist.yml                        ← user-edited URL list
    └── observations.db                      ← SQLite, single file
```

`C:\IMDR_LOCAL\` convention: any future fast-polling utility goes under `C:\IMDR_LOCAL\<utility>\`. Captured in memory.

#### Watchlist file

Plain text, one Polymarket event URL or bare slug per line, `#` for comments. **Hot-reloaded on every poll** — the user can add or remove URLs while the loop is running and the next poll picks up the change without a restart.

```
# --- Fed / rates ---
https://polymarket.com/event/fed-decision-in-april
https://polymarket.com/event/who-will-be-confirmed-as-fed-chair
https://polymarket.com/event/how-many-fed-rate-cuts-in-2026

# --- Iran / Hormuz ---
https://polymarket.com/event/will-the-iranian-regime-fall-by-april-30
https://polymarket.com/event/strait-of-hormuz-traffic-returns-to-normal-by-april-30
...
```

Currently seeded with **25 macro-relevant events** spanning Fed/rates (4), Iran/Hormuz (6), Russia/Ukraine (3), Trump/US politics (2), China/Taiwan (1), Israel/Middle East (2), oil & commodities (3), recession (1), midterms (3).

#### Auto-discovered cache (complements the manual watchlist)

In addition to `watchlist.yml`, `streaming.py loop` periodically scans Gamma `/tags` and the most-active `/events` for macro-relevant slugs and writes them to `C:\IMDR_LOCAL\polymarket\auto_discovered.json`. On every poll, the slug list is the **union of manual + discovered** (manual wins on dedup, so curated section/asset-tag assignments are preserved).

| Knob | Default | Notes |
|------|--------:|-------|
| `DISCOVERY_REFRESH_SEC` | `3600` | Refresh the cache no more than once per hour. |
| `DISCOVERY_MIN_VOLUME` | **`1_000.0`** | Floor on `volume24hr` (rolling 24h). Lowered from `50_000` → `1_000` on 2026-04-29 — sibling Iran/Hormuz markets sit at $1.5K–$31K 24h vol and were being missed by the prior floor. Tag and exclude regexes still gate sports/entertainment/penny noise. |

Force a refresh with `python -m scripts.prediction.polymarket.streaming discover`. Skip discovery on a loop with `--no-discover` (manual-only).

Auto-discovered slugs land in the **`uncurated`** asset bucket in the email (no section header → default tag). The polywatch email caps this bucket at `MAX_UNCURATED_PER_EMAIL = 10` events with overflow surfaced in a footer line.

#### SQLite schema (3 tables)

`market_observation` — atomic price observation, one row per (snapshot, market). Hot append target. PK on `(snapshot_ts, condition_id)`, indexed on `(event_id, snapshot_ts)` and `(snapshot_ts)` for spike-detection queries.

`poll_log` — one row per poll. `raw_response_json` is populated **only when the poll errored** (chunk_errors non-empty). Persisting the full Gamma payload on every success poll blew the DB to 18 GB in <30 days and held an exclusive VACUUM lock long enough to take down the streaming loop; the diagnostic value never compensated. Cleanup strips the column on any kept success row as a regression guard.

`watchlist` — `(slug, event_id, first_added_ts, last_seen_ts, removed_ts)`. Tracks slug lifecycle so we can answer "when did we start watching this?" and "when did the event resolve / drop off the watchlist?" without leaving the DB.

All three created via `CREATE TABLE IF NOT EXISTS` at every script start. Zero migration ceremony.

#### One consolidated module — three subcommands

[scripts/prediction/polymarket/streaming.py](../../scripts/prediction/polymarket/streaming.py) — single file, ~370 lines, three CLI subcommands:

```
python -m scripts.prediction.polymarket.streaming poll                       # one-shot single poll
python -m scripts.prediction.polymarket.streaming loop --interval 300        # daemon, polls every N sec
python -m scripts.prediction.polymarket.streaming cleanup                    # 7-day purge + VACUUM + summary (run daily via imdr_daily.py)
```

Internally `poll`, `loop`, and `cleanup` share `load_watchlist()` (from the shared `watchlist` module), `open_db()`, `poll()`, and `purge_and_vacuum()` helpers.

**Loop behaviour:**
- Reloads `watchlist.yml` from disk on every iteration (hot-reload).
- Catches per-iteration exceptions, logs, continues — no death on single failure.
- Heartbeat line every 12 polls.
- Graceful Ctrl+C: commit pending transaction, close DB, exit 0.
- Configurable interval via `--interval`, clamped to [60, 1800]. Default 300 (5 min).

**Cleanup behaviour:** (runs **daily** — wired into [`scripts/imdr_daily.py`](../../scripts/imdr_daily.py) immediately before the `barclays_skew` vendor feed)
- `DELETE FROM market_observation WHERE snapshot_ts < datetime('now', '-7 days')` — 7-day rolling window (was 30 days; truncated 2026-05-19 after the raw_response_json bloat episode).
- Same for `poll_log`.
- `UPDATE poll_log SET raw_response_json = NULL WHERE http_ok = 1` — regression guard against the bloat returning if some future change re-introduces always-on payload capture.
- Marks watchlist slugs as auto-removed if `last_seen_ts` is older than the retention window.
- `VACUUM` to reclaim file space.
- Prints a summary: rows removed per table, DB size before/after, oldest/newest remaining row, active slugs count.

The cadence (daily) keeps the rolling window tight — expired rows are pruned within ~24h of crossing the boundary. With raw_response_json now error-only, DELETE+VACUUM is sub-second on a healthy DB.

**Important Gamma quirk:** the `/events` endpoint defaults to `limit=20`. If the watchlist exceeds 20 slugs, only 20 events come back. The script passes `limit=max(2*N, 100)` explicitly to avoid this.

#### Volume sanity at 30-day rolling retention

| Cadence | Polls/day | Rows/day in `market_observation` | DB file size at 30d | DB size/year |
|---------|----------:|---------------------------------:|--------------------:|-------------:|
| 60s | 1,440 | ~72k → ~210k* | ~210 MB | rolling, capped |
| 5m | 288 | ~14k → ~40k* | ~60 MB | rolling, capped |
| 10m | 144 | ~7k → ~20k* | ~30 MB | rolling, capped |
| 30m | 48 | ~2.5k → ~7k* | ~10 MB | rolling, capped |

*Updated estimates with the 25-event watchlist and ~190 markets/poll.

#### Spike-detection SQL (one-liner, runs in step 3)

```sql
WITH ordered AS (
    SELECT condition_id, snapshot_ts, yes_price, spread,
           LAG(yes_price)   OVER (PARTITION BY condition_id ORDER BY snapshot_ts) AS prev_yes,
           LAG(snapshot_ts) OVER (PARTITION BY condition_id ORDER BY snapshot_ts) AS prev_ts
    FROM market_observation
    WHERE snapshot_ts >= datetime('now', '-60 minutes')
)
SELECT condition_id, prev_ts, snapshot_ts, prev_yes, yes_price,
       yes_price - prev_yes AS delta
FROM ordered
WHERE prev_yes IS NOT NULL
  AND ABS(yes_price - prev_yes) >= 0.05
  AND COALESCE(spread, 0) <= 0.20;
```

That query plus a small print formatter is the watcher's whole "show moves" pass. Step 3 wraps this with a console / log / alert surface.

#### Verified end-to-end on first build (2026-04-27)

- 25 watchlist slugs → 25 events resolved → 232 markets seen → 192 observations written per poll.
- 11 polls at 60s cadence ran clean; loop 7+ picked up the watchlist expansion (11 → 25 slugs) without restart.
- Daily run on a synthetic 60-day-old row deleted it cleanly and shrank the DB after `VACUUM`.

---

## Watchlist composition (legacy regex approach — deprecated)

Macro relevance is defined by **tag matching**, not question keyword. Tags are sharper because Polymarket curators assign them per topic. The filter lives at the top of [scripts/explore/polymarket_macro_stream.py](../../scripts/explore/polymarket_macro_stream.py):

- `MACRO_RE` — patterns matched against tag `label` / `slug` (case-insensitive). Covers macro / economy / GDP / recession / employment / Fed / FOMC / rates / interest / inflation / CPI / PCE / oil / crude / OPEC / tariffs / trade / China / Russia / Ukraine / Iran / Israel / Hormuz / Taiwan / geopolitics / elections / politics / Congress / midterm / Democrat / Republican / central bank / ECB / BOE / BOJ / PBOC / RBA / RBNZ / debt ceiling / budget / shutdown / fiscal / Starmer / Macron / Merz / Scholz / Xi / Putin / Zelensky.
- `EXCLUDE_RE` — sports / entertainment kill list: FIFA / World Cup / Olympics / NBA / NFL / MLB / NHL / Super Bowl / Oscar / Grammy / Tony / Bachelor / GTA / Heisman / ESPYs / Emmy / Netflix / Spotify / Golden Globe / Formula 1 / Eurovision / Love Island.
- `MIN_VOLUME = $1,000` — drops dead markets.

**Currently produces ~42 events across 7 themes (~$7.3M aggregate volume):**

| Theme | Events | Aggregate volume |
|-------|------:|-----------------:|
| Macro Indicators | 24 | $2.55M |
| GDP | 9 | $0.89M |
| Macro Single | 3 | $1.04M |
| interest rates | 3 | $1.19M |
| Macro Graph | 1 | $1.38M |
| Thailand Election | 1 | $0.19M |
| RBA | 1 | $0.02M |

**Top events by volume in the most recent capture** (2026-04-24 PM):

- US recession by end of 2026 — modal: YES @ 26.0%, $1.38M
- What will Fed Rate hit before 2027 (18-market path) — modal: 3.25% @ 66.5%, $1.35M
- Bank of Japan decision in April (4-market grid) — modal: no change @ 97.5%, $1.10M
- Fed rate hike in 2026 — modal: YES @ 12.5%, $0.92M
- How high will inflation get in 2026 (6-market grid) — modal: >3.5% @ 90%, $0.45M
- China Annual GDP Growth 2026 (10-market grid) — modal: 4–5% @ 75.5%, $0.42M

## Operational — Step 2 (current) watcher

### One-shot poll

```
python -m scripts.prediction.polymarket.streaming poll
```

Reads `C:\IMDR_LOCAL\polymarket\watchlist.yml`, makes one Gamma `/events` call, writes one row per active market into `observations.db`, plus a `poll_log` entry with the raw response. Completes in ~100–500 ms.

### Continuous daemon

```
python -m scripts.prediction.polymarket.streaming loop --interval 300
```

Polls every `--interval` seconds (clamped to 60–1800). Hot-reloads `watchlist.yml` on every iteration. Heartbeat line every 12 polls. Graceful Ctrl+C. Catches per-iteration exceptions and continues.

#### Scheduling — run continuously, restart once a day

The watcher is designed to run effectively 24/7 with one clean restart per day for hygiene (memory drift, picks up code changes). The pattern is **daily Task Scheduler trigger + "Stop the existing instance" multiple-instance policy** — when the daily trigger fires, Task Scheduler kills any prior instance and starts a fresh one.

Task Scheduler invokes the IMDR conda Python directly — same pattern as every other Python task in this repo. No PowerShell wrapper needed.

| Setting | Value |
|---|---|
| Name | `Polymarket Streaming Watcher` |
| Trigger | Daily at 06:00 (local) |
| Program/script | `python` |
| Add arguments | `-m scripts.prediction.polymarket.streaming loop --interval 300` |
| Start in (optional) | `z:\Business\Personnel\Arjun\GitHub\IMDR` *(IMDR repo root, so `python -m scripts.prediction...` resolves)* |
| Run as | current user, Interactive logon |
| If task is already running → | **Stop the existing instance** *(this is the key setting — gives the once-a-day restart)* |
| Start when available | **enabled** *(picks up if the machine was off at trigger time)* |
| Execution time limit | **none / unlimited** *(we want the loop to run all day)* |
| Stop if computer switches to battery | **disabled** *(if running on a laptop)* |

Manual triggers (PowerShell):

```powershell
# Start now (don't wait for the daily trigger)
Start-ScheduledTask -TaskName 'Polymarket Streaming Watcher'

# Inspect last run state — Last Result 0 = success, 267009 = still running
Get-ScheduledTask -TaskName 'Polymarket Streaming Watcher' | Get-ScheduledTaskInfo

# Stop without removing
Stop-ScheduledTask -TaskName 'Polymarket Streaming Watcher'
```

Or from CMD: `schtasks /run /tn "Polymarket Streaming Watcher"`, `schtasks /query /tn "..." /v /fo list`.

**No on-disk log files.** stdout from the loop is consumed by Task Scheduler and not redirected anywhere. The DB (`market_observation` and `poll_log` tables) is the source of truth — that's where every poll's state and any error is recorded. To verify health, query the DB:

```cmd
sqlite3 "C:\IMDR_LOCAL\polymarket\observations.db" "SELECT MAX(snapshot_ts), COUNT(*) FROM market_observation"
```

Latest snapshot within the last 5 min → healthy. Older → loop is wedged or computer was off; check Task Scheduler History tab for the cause.

### Daily cleanup (30-day rolling retention)

```
python -m scripts.prediction.polymarket.streaming cleanup
```

Deletes observations and poll-log entries older than 30 days, marks watchlist slugs as auto-removed if not seen in 30 days, runs `VACUUM`, prints summary. Idempotent.

**Wired into [`scripts/imdr_daily.py`](../../scripts/imdr_daily.py)** — runs once a day immediately before the `barclays_skew` vendor feed. No separate Task Scheduler entry needed; the polymarket cleanup rides whichever schedule already invokes the IMDR daily orchestrator.

---

## Operational — Step 2 (orig, superseded) snapshot job

### Run the snapshot

```
python -m scripts.explore.polymarket_event_snapshot
```

Completes in ~7 seconds. Idempotent within a minute (re-runs in the same minute overwrite the same `HHMM` file). Writes a JSONL and updates the per-date manifest.

### Run the analytics

```
python -m scripts.explore.polymarket_event_analytics
```

Reads every snapshot ever written under `data/cache/polymarket/snapshots/` and regenerates the three reports. Idempotent — same panel produces byte-identical reports.

### Schedule (intended, not yet wired)

Two daily snapshot runs at 12:00 UTC and 20:00 UTC, the same mechanism as the existing IMDR schedulers ([scripts/imdr_daily.py](../../scripts/imdr_daily.py), [scripts/imdr_hourly.py](../../scripts/imdr_hourly.py)). Analytics can run ad-hoc or be chained after the PM snapshot.

---

### Step 3 — Polywatch (move-detection runtime + email alerts)

Step 2 produces a stream of observations. **Polywatch** ([scripts/prediction/polymarket/polywatch.py](../../scripts/prediction/polymarket/polywatch.py)) is the analytics layer that sits on top: it reads `observations.db`, classifies meaningful price moves on each watchlisted event, and emits an HTML email alert with deep links to the underlying Polymarket events.

#### Why a separate process

Polywatch runs as its **own** process alongside `streaming.py loop`. The collector stays dumb (poll → write rows → exit) and the detector reads its own state from the same SQLite file but never touches the collector's tables. Two reasons:

1. **Replayability.** Detection logic can be re-run over historical observations (`backfill --since`) without re-polling the API or perturbing the live state machine.
2. **Resilience.** A polling outage doesn't break detection logic; a detector bug doesn't drop incoming observations.

```
streaming.py loop  ─►  observations.db  ◄─  polywatch.py loop  ─►  send_outlook_email()
  (collector)            (SQLite)            (detector + emailer)        (existing)
```

Ownership of tables in the shared SQLite file:

| Table | Owner | Purpose |
|-------|-------|---------|
| `market_observation` | streaming.py (writes), polywatch.py (reads) | Per-snapshot, per-market price observation |
| `poll_log`           | streaming.py | API call log |
| `watchlist`          | streaming.py | Slug-level last-seen tracking |
| **`alert_state`**    | **polywatch.py** | Per-event last-alert state (cooldown / re-arm) |
| **`alert_log`**      | **polywatch.py** | Append-only log of every classified detection (emitted *and* suppressed) |

#### Alert classes

For each event with observations in the latest snapshot, polywatch identifies the **modal market** = the market with the highest `yes_price`. Classification operates on this modal market:

| Class | Trigger | Default | Meaning |
|-------|---------|---------|---------|
| **SPIKE** | \|Δ modal_yes\| ≥ spike threshold vs prior snapshot | 10pp | Sudden move — tape bomb, news drop |
| **MODAL_FLIP** | Modal `condition_id` changed vs prior snapshot | (any) | Leading outcome flipped — regime change |
| **DRIFT** | \|Δ modal_yes\| ≥ drift threshold over rolling lookback | 15pp / 6h | Slow trend the SPIKE check would miss |
| **VOL_BURST** | `volume_24h / median(volume_24h, 7d)` ≥ ratio | 5× | Activity surge — real interest behind the price |

An event can fire multiple classes in one cycle (a SPIKE + VOL_BURST is the strongest signal: news-driven price move with concurrent volume confirmation).

#### Suppression rules

Two reasons polywatch deliberately swallows a classified detection:

1. **Liquidity guard (ILLIQUID).** If the modal market's spread > 20pp, the alert is logged with `suppressed='ILLIQUID'` and not emailed. Wide-spread markets generate phantom moves at the print level — sending those alerts trains the desk to ignore the channel. The detection still appears in `alert_log` so you can audit how often a watched event is illiquid.

2. **Cooldown / re-arm.** If a non-suppressed alert fired for the same `event_id` within the last 30 minutes, the next alert is suppressed *unless* the modal_yes has moved another ≥ 5pp from the value at the last alert. This prevents a single 30-minute trending move from spamming twelve emails on a 5-minute polling cadence, without losing the second leg of a multi-stage move.

#### CLI

```
python -m scripts.prediction.polymarket.polywatch detect
    # one-shot: read latest snapshot, classify, send email if anything triggers, exit

python -m scripts.prediction.polymarket.polywatch loop --interval 300
    # daemon: detect every --interval seconds (clamped 60–1800)

python -m scripts.prediction.polymarket.polywatch backfill --since 2026-04-26
    # replay detection over historical observations
    # writes alert_log only (NOT alert_state) to leave the live state machine untouched
    # NO email sent — for tuning thresholds against real history
```

All threshold knobs are CLI-overridable on `detect` and `loop`:

```
--spike-threshold 0.10        # |Δ| modal_yes vs prior snapshot
--drift-threshold 0.15        # |Δ| modal_yes over rolling lookback
--drift-lookback-hours 6
--vol-burst-ratio 5.0         # 24h vol / 7d median 24h vol
--illiquid-spread 0.20        # suppress alerts above this spread
--cooldown-minutes 30
--rearm-delta 0.05            # min further |Δ| to re-alert within cooldown
--no-email                    # detect/loop only, no email send
```

#### Email shape

Sent via the existing IMDR notifications path ([src/imdr/notifications/email.py](../../src/imdr/notifications/email.py) → Outlook COM). Recipient: `settings.email_to` (no new settings field needed). Importance escalates to `2` (high) when the cycle contains any SPIKE or MODAL_FLIP; otherwise `1`.

**Subject example:**
```
[Polywatch] 3 event(s) moving | 2 SPIKE, 1 VOL_BURST | 2026-04-29
```

**Body layout** (restructured 2026-04-29 — see "Email restructure" below):

- Dark-navy header bar + coloured status badge (red on critical, amber on drift-only, green on quiet).
- Summary table — counts per alert class.
- **Per asset bucket** (`oil_mena`, `fx_safehaven_eur`, `equity_il_mena`, `equity_china_taiwan`, `fx_political_eu`, `political_us`, `uncurated`, in canonical order): a labeled section with each event rendered as a card.
- **Per event card**: title rendered as a link to `https://polymarket.com/event/{slug}` + a row of coloured **alert badges** (SPIKE / MODAL_FLIP red, DRIFT amber, VOL_BURST purple, ILLIQUID gray) followed by a **child-markets sub-table** showing every sub-market's question, YES probability, Δ vs prior snapshot, 24h volume and spread. Modal row is bolded and shaded; non-modal rows show the same metrics so the desk sees the full breakdown.
- Per-row pills: `→ NEW LEADER` (green, on the new modal child when MODAL_FLIP fires), `was leader` (gray, on the prior modal), `NEW` (blue, when a child appeared after the prior snapshot), `RESOLVED` (gray, when a child's YES is pinned within the resolved band).
- Footer prints the threshold settings actually applied for this run, so a recipient can A/B threshold changes by reading the email rather than the code.

##### Email restructure (2026-04-29)

The original layout grouped detections by alert class (SPIKE / MODAL_FLIP / DRIFT / VOL_BURST), nested by asset bucket, and rendered only the modal market per event. Multi-market events lost their breakdown — e.g. *"What Iranian demands will Trump agree to in April?"* (4 children: Enrichment, Oil Sanction Relief, Hormuz Transit Fees, Unfreeze Assets) showed only the leading child.

Three behavioural changes:

1. **Top-level grouping flipped** from alert class → **asset bucket**. Same canonical order via `ASSET_TAG_ORDER` in [polywatch_alert.py](../../src/imdr/notifications/formatters/polywatch_alert.py).
2. **Multi-market events render every child** as a sub-table. Children are computed on-the-fly from `market_observation` at email-send time — no migration; `alert_log` stays modal-only as the audit record. Trade-off: emails can't be regenerated past the 30-day market_observation retention. Documented in the polywatch.py module docstring.
3. **Alert classes become badges** on the event header instead of the section heading.

Implementation knobs (constants in `polywatch_alert.py`):

- `MAX_CHILDREN_PER_EVENT = 8` — cap the children table; truncated rows surfaced via "+N child markets with smaller moves not shown" footer line. Modal + new-leader rows are **always** retained even if their `|Δ|` falls outside the cap.
- `MAX_UNCURATED_PER_EMAIL = 10` — cap the auto-discovered bucket so the email stays skim-able; overflow surfaced via "+N more uncurated events suppressed" line at the section foot.

Sort order within each bucket: events sorted by `max(|child Δ|)` descending. Within an event card, children sorted by `|Δ|` descending (not by yes price), so the largest mover appears first regardless of whether it's the modal child.

Detector changes:

- New `ChildRow` dataclass + `event_children_at()` helper in [polywatch.py](../../scripts/prediction/polymarket/polywatch.py) — fetches all sub-markets per event at a snapshot, joins prior snapshot for per-child deltas, marks `is_modal` / `was_modal` / `is_resolved`.
- `DetectionResult.child_markets` field, populated in `detect_at`. `send_email_for` is a pure render — no new SQL there.
- Detection logic is unchanged: classification (SPIKE / DRIFT / VOL_BURST / MODAL_FLIP) still operates on the modal market only. Children are display-only.

Tests: 4 new in [test_polywatch_detector.py](../../tests/unit/test_polywatch_detector.py) (`test_event_children_at_returns_all_children_yes_desc`, `test_alert_carries_child_markets_with_per_child_deltas`, `test_child_marked_new_when_prior_snapshot_missing_it`, `test_child_table_sorted_by_abs_delta_in_formatter`). 14/14 polywatch tests pass.

#### Tuning workflow

The `backfill` subcommand is the threshold-tuning tool:

```
# Compare current defaults against the last week of observations.
python -m scripts.prediction.polymarket.polywatch backfill --since 2026-04-20

# Try a tighter SPIKE threshold over the same window.
python -m scripts.prediction.polymarket.polywatch backfill --since 2026-04-20 --spike-threshold 0.05
```

`backfill` writes per-replay rows to `alert_log` (so they're queryable later) but deliberately does **not** update `alert_state`. The live cooldown machine is unaffected, and the same window can be replayed any number of times with different thresholds without polluting state.

#### Verified end-to-end

First successful run 2026-04-27 against ~5h of real observations (53 snapshots, 38 events): detector identified 5 VOL_BURST hits on the Bitcoin-vs-Gold-vs-S&P event (high relative volume) and 1 MODAL_FLIP on the next French Presidential Election (closely-contested race, leader changed). No false SPIKEs against 5pp of intraday noise. 6/6 unit tests in [tests/unit/test_polywatch_detector.py](../../tests/unit/test_polywatch_detector.py) pass.

#### Operations

Detailed operations runbook lives in [polywatch_operations.md](polywatch_operations.md): how to run alongside `streaming.py`, how to inspect `alert_log`, how to tune thresholds via backfill, troubleshooting common alert-spam / illiquid-suppression patterns.

---

## Key files

```
scripts/prediction/polymarket/
├── streaming.py                      Step 2 (current) — poll | loop | cleanup subcommands
└── polywatch.py                      Step 3 — detect | loop | backfill subcommands

src/imdr/notifications/
├── formatters/polywatch_alert.py     Step 3 — Jinja2 + dataclass alert formatter
└── templates/polywatch_alert.html    Step 3 — alert email template

tests/unit/test_polywatch_detector.py Step 3 — 6 in-memory SQLite detector tests

scripts/explore/                       (Step 1 + Step 2 (orig) artefacts — kept for reference)
├── explore_polymarket_gamma.py       Step 1 first-touch (run-once)
├── polymarket_macro_stream.py        Step 1 live WS tape (dev artefact, source of helpers)
├── polymarket_event_snapshot.py      Step 2 (orig) — superseded
└── polymarket_event_analytics.py     Step 2 (orig) — superseded

scripts/imdr_daily.py                  ← invokes `scripts.prediction.polymarket.streaming cleanup` daily (before barclays_skew)

src/imdr/connectors/http.py           Reusable HTTPClient (httpx + retry/logging)

C:\IMDR_LOCAL\polymarket\             ← Step 2 (current) + Step 3 data — outside IMDR repo and DB
├── watchlist.yml                     user-edited URL list, hot-reloaded
└── observations.db                   SQLite — owned by streaming.py: market_observation, poll_log, watchlist
                                                 owned by polywatch.py: alert_state, alert_log

data/cache/polymarket/                ← Step 1 + Step 2 (orig) artefacts, deprecated but kept
├── markets_sample.json               Step 1 cache
├── events_sample.json                Step 1 cache
├── macro_hits.json                   Step 1 cache
├── frequency_probe.json              Step 1 cache
├── watchlist.json                    Step 1 stream watchlist
├── stream.jsonl                      Step 1 raw WS log
├── snapshots/{YYYY-MM-DD}/           Step 2 (orig) — 2x/day JSONL panels
│   ├── snapshot_HHMMZ.jsonl          one line per event per snapshot
│   └── manifest.json
└── analytics/                        Step 2 (orig) — move classification / theme rollup / stats
    ├── move_classification_{date}.md
    ├── theme_rollup_{date}.md
    └── event_stats.md

pyproject.toml                        +websockets>=13.0 (used by polymarket_macro_stream.py)
```

## What we deliberately have not done

- **No IMDR MSSQL `prediction` schema for the watcher.** The desk explicitly directed this to `C:\IMDR_LOCAL\` — local utility, not part of IMDR's DB footprint. Promotion to MSSQL only happens if cross-team access ever becomes a requirement (and even then, the SQLite schema is intentionally MSSQL-portable).
- **No DuckDB / no Parquet archive.** SQLite is sufficient at the volumes involved (≤210 MB at the most aggressive 60s cadence with 30-day retention).
- **No alerting / no email / no Slack.** ~~Step 5.~~ Email alerting is now Step 3 (Polywatch). Slack/Teams is Step 3.5 — deferred but designed for.
- **No WebSocket in the production path.** Step 1 proved it works, but the desk's consumption rhythm is HTTP-poll cadence — streaming adds machine effort with no marginal value at 5-min cadence.
- **No cross-asset correlation against IMDR rates/FX yet.** Step 4 — needs the panel to grow first.
- ~~**No move-detection runtime yet.** Step 3 — the spike-detection SQL is in the doc and validated against the schema, but the watcher loop currently only ingests; it doesn't yet emit "X moved Y pp" lines.~~ **Done — see Step 3 (Polywatch).**
- **No order-book depth or CLOB historical backfill.** Step 6.
- **The deprecated 2x/day artefacts and analytics under `data/cache/polymarket/snapshots/` and `data/cache/polymarket/analytics/` are not migrated.** They remain on disk, untouched, as a historical record of the prior approach.

## Known imperfections worth revisiting

- The macro tag filter currently catches some adjacent noise (e.g. `house-races`, `2024-us-presidential-election` tags persist after their events resolve). They produce zero markets so don't pollute the watchlist, but worth pruning when the tag list stabilises.
- `implied_prob_sum` deviates from 1 on a meaningful minority of events. Min observed 0.137, max 1.908. Two regimes: (i) tail outcome unpriced (sum < 1, real signal), (ii) markets aren't mutually exclusive (sum > 1, e.g. cumulative price-strike events). Worth a manual audit when the panel grows.
- Snapshot schedule is hard-coded at top of file. Once Windows Task Scheduler entries exist, treat the schedule as defined externally and drop the constant.
- The 5-minute test panel produced 0 BIG_MOVE / 0 MOVE / 0 DRIFT classifications, all 31 FLAT + 11 ILLIQUID. Expected — too short. Real validation comes after ≥ 1 week of AM/PM captures.
