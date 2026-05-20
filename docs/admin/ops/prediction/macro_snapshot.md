# Polymarket Macro Snapshot

_Last updated: 2026-05-04_

A daily / on-demand HTML one-pager that gives the desk a single-glance view of
the macro and event-driven cross-section being priced on Polymarket: oil &
geopolitics, US data + Fed, Europe / G10 central banks, an Asia overlay
(BoJ / BoK / RBA / RBNZ / China-Korea-Japan data), and tariff binaries.

It sits on top of the same `observations.db` that
[`streaming.py`](../../scripts/prediction/polymarket/streaming.py) writes and
[`polywatch.py`](../../scripts/prediction/polymarket/polywatch.py) reads — the
snapshot is a **read-only report**, no DB writes, no email send.

## What's in it

A single HTML table grouped into sections:

| Section | What lives here |
|---|---|
| **Geopolitics / Oil** | Iran/Hormuz, Israel-MENA, Russia-Ukraine binaries — the same oil/EUR-haven set that the watchlist tracks. |
| **US Data & Fed** | NFP, Unemployment Rate, CPI Y/Y + M/M, Q2 GDP, recession-by-EOY, FOMC dissents, Powell-out, court-tariff-refund. |
| **Europe / G10 CB** | ECB June, BoE June, RBA May + June. |
| **Asia Overlay** | BoJ June + July, BoK May + July, RBNZ May + July, China Q2 GDP, S Korea Q2 GDP, Japan Q1 GDP, India 2026 inflation, Trump-visits-China, Taiwan / China-Japan tail. |
| **Tariffs / Trade** | Canada tariff binaries. |
| **Recently Resolved** | Auto-populated: rows whose underlying release/decision happened in the last `RECENT_RESOLVED_DAYS` (default 5). Useful for seeing how the actual print moved the modal bucket on resolution day. Drops off automatically once past the window. |

### Forward-vs-resolved classification

Each watchlist entry carries an `event_date` — the underlying release / decision /
resolution date. The generator routes the row by comparing it to the latest
snapshot's UTC date:

- `event_date is None` → open-ended (e.g. "Israel strikes 3+ countries in 2026"); always shown in its native section.
- `event_date >= today` → upcoming; native section.
- `today − event_date ≤ RECENT_RESOLVED_DAYS` → quarantined under **Recently Resolved**.
- older than that → dropped (and listed in the footer's "Dropped" line for audit).

The quarantine exists because Polymarket markets don't resolve instantly — the
modal bucket converges to ~100/0 over hours/days, and the Δ6h on resolution
day is often the most informative metric in the snapshot.

Each row shows:

- **Asset tag** (Oil / USD / EUR / JPY / KRW / CNH / …) — what desk the row is for.
- **Event** — clickable link to the Polymarket page (when slug is known).
- **Modal sub-question** — the most-likely outcome bucket (e.g. "Will the April 2026 unemployment rate be 4.3%?").
- **Tail** — top-2 secondary buckets with ≥5% probability, so two-way risk is visible (e.g. BoJ June: 51.5 / 50.4 coin flip).
- **Consensus %** — modal-bucket Yes price.
  - Annotated with the **decisiveness gap** = modal − second-mode bucket. ≤5pp shows `· two-way` in red (coin flip — flippable on news); ≥30pp green (entrenched — stale unless something cracks).
- **Δ6h** / **Δ24h** / **Δ7d** — modal-condition Yes change at three horizons: intraday (catches news that just hit), daily (overnight + session), weekly (trend). For tail markets (prior <20% or >80%), Δ6h and Δ24h get a `+/−Y% rel` subnote when `|Δ| ≥ 0.5pp` — captures regime shifts that pp underplays (e.g. Taiwan 7%→14% is +7pp but +100% in odds). Mid-range markets show pp only.
  - Reading the trio: a Δ6h that exceeds Δ24h means the move is fresh (just-broke news); Δ6h opposing Δ24h means an intraday reversal; Δ7d aligned with Δ24h confirms a trend.
- All three columns show `n/a` until streaming history has covered the window for that event's modal condition.
- **Vol 24h** — sum of all sub-market 24h volumes.
  - **Burst badge** = modal-condition vol_24h ÷ 7d-median baseline. Shown only when ≥1.5× (orange `Nx burst` — desk attention spike) or ≤0.5× (gray `Nx quiet` — market dead today). 0.5–1.5× is normal and unflagged. Same metric polywatch uses for VOL_BURST detection.
- **Market read** — one-sentence editorial pinned to the row in the curation contract.

### Reading the metrics together

The four annotations work as a triage:

1. **Two-way tag + Δ24h moving** = a coin flip is shifting; the trade is on. (BoJ June at 51.5/50.4 with a meaningful Δ24h is the canonical "act now" signal.)
2. **Entrenched tag + flat Δ** = consensus is settled; nothing to do unless your view differs from market.
3. **Burst badge + flat Δ** = the desk is paying attention but consensus hasn't moved — positioning churn ahead of an event.
4. **Tail market with `Nx% rel` move** = small pp can be a big regime shift; check the underlying news.

## Output convention

```
C:\IMDR_LOCAL\polymarket\snapshots\macro_snapshot_<YYYYMMDD>_<HHMM>.html
```

Timestamp is the **snapshot's own ts** (UTC), not generation time — so re-running
against the same snapshot overwrites in place rather than creating duplicates.
The HTML body also stamps `generated: <UTC now>` for audit.

## How to run

```
python -m scripts.prediction.polymarket.macro_snapshot
```

Optional flags:

- `--db PATH` — point at a different SQLite (defaults to `C:\IMDR_LOCAL\polymarket\observations.db`).
- `--out-dir PATH` — different output dir (defaults to `C:\IMDR_LOCAL\polymarket\snapshots`).

Open the resulting HTML in any browser. Each event title links to the
Polymarket page; the per-row modal question and tail buckets are inline so a
reader doesn't need to click through.

## How the contract is edited

The set of events shown lives in [`watchlist.yml`](watchlist_format.md)
(`C:\IMDR_LOCAL\polymarket\watchlist.yml`) — the same file consumed by
`streaming.py` and `polywatch.py`. Snapshot rendering requires `section`,
`label`, `asset`, `market_read`. Optional: `event_date`, `event_id`, `slug`
(suffix `*` for fuzzy match).

To add a row:

1. Add an entry to `watchlist.yml`. Use `event_id` if you have it (preferred);
   otherwise `slug` — exact match, or a prefix with trailing `*` for events
   Polymarket hasn't posted yet (e.g. `slug: how-many-jobs-added-in-may-*`
   auto-binds May NFP once it goes live).
2. Set `event_date` to the underlying release / decision / resolution date (this
   drives the upcoming-vs-resolved-vs-stale routing). Omit for open-ended
   events without a clear date.
3. Set the editorial fields: `section` (display group), `label`, `asset`,
   `market_read`.
4. Re-run the generator. Stale rows fall off on their own.

The "market read" string is **editorial** — the desk's standing view of what
the consensus level *means*, not auto-derived. Re-edit it when the regime
changes (e.g. once Fed is cutting again, the Powell-out read should flip from
"policy-uncertainty premium" to something else).

## Coupling with `polywatch` and `streaming`

All three scripts (`streaming.py`, `polywatch.py`, `macro_snapshot.py`) load
the same `watchlist.yml` via the shared loader at
[`scripts/prediction/polymarket/watchlist.py`](../../scripts/prediction/polymarket/watchlist.py).
There's no longer config drift between "what gets streamed" and "what shows
in the snapshot": adding an editorial entry automatically also enrolls it
in polling.

Polling-only entries (no `section/label/asset` fields) are valid — they're
streamed and bucketed for polywatch alerts but don't render in the snapshot.
