# Polywatch — Operations Runbook

_Last updated: 2026-04-29_

The detector that sits on top of [`streaming.py`](../../scripts/prediction/polymarket/streaming.py) and emails the desk when watchlisted Polymarket events make a meaningful move. See [polymarket_buildout.md](polymarket_buildout.md) Step 3 for the design rationale.

## What it does

Polywatch reads `C:\IMDR_LOCAL\polymarket\observations.db`, identifies the modal market for each watchlisted event in the latest snapshot, classifies any move into one of four classes (SPIKE / MODAL_FLIP / DRIFT / VOL_BURST), suppresses illiquid-market noise and post-alert spam via cooldown rules, and sends a single Outlook email per cycle when anything emittable triggers. Each event in the email is a clickable link to its Polymarket page.

### Email layout (since 2026-04-29)

The email body is grouped **by asset bucket** (`oil_mena`, `fx_safehaven_eur`, `equity_il_mena`, `equity_china_taiwan`, `fx_political_eu`, `political_us`, `uncurated`), not by alert class. Each event card shows:

- The event title as a clickable Polymarket link.
- A row of **alert badges** (SPIKE / MODAL_FLIP red, DRIFT amber, VOL_BURST purple, ILLIQUID gray).
- A **child-markets sub-table** — every sub-market's question, YES probability, Δ vs prior snapshot, 24h volume and spread. Rows sorted by `|Δ|` desc, modal child bolded and shaded. Pills surface state changes: `→ NEW LEADER` (new modal child after MODAL_FLIP), `was leader` (prior modal), `NEW` (child appeared after the prior snapshot), `RESOLVED` (YES pinned within band).

Multi-market events that previously rendered as a single modal-question card now show every child. For multi-child events with >8 children, only the top 8 by `|Δ|` are rendered with a "+N more" footer line; the modal and new-leader rows are always retained. The `uncurated` bucket (auto-discovered slugs) is capped at 10 events per email.

Children are computed on the fly from `market_observation` at email-send time. `alert_log` remains modal-only. Replaying alerts older than the 30-day market_observation retention loses sub-market context (documented in the polywatch.py module docstring).

## Daily run

Polywatch runs as a separate process **alongside** `streaming.py loop`. Two terminals (or two scheduled tasks):

```
# Terminal 1: collector — polls Polymarket every 15 minutes
python -m scripts.prediction.polymarket.streaming loop --interval 900

# Terminal 2: detector — checks for moves every 15 minutes
python -m scripts.prediction.polymarket.polywatch loop --interval 900
```

Recommended cadence: same interval as the poller (15 minutes default). Faster doesn't help — there's no new snapshot to evaluate.

Logs go to stdout for both processes. The detector loop self-throttles: if no new snapshot has appeared since the last cycle, the cycle is a quiet skip (no email, heartbeat line every 12 cycles).

## Tuning thresholds

The `backfill` subcommand replays detection over historical observations **without** sending email or perturbing live state. This is the right tool to A/B threshold changes before promoting them.

```
# How does the current default config look against the last week?
python -m scripts.prediction.polymarket.polywatch backfill --since 2026-04-20

# Try a tighter SPIKE threshold over the same window.
python -m scripts.prediction.polymarket.polywatch backfill --since 2026-04-20 --spike-threshold 0.05

# Try a longer drift window.
python -m scripts.prediction.polymarket.polywatch backfill --since 2026-04-20 --drift-lookback-hours 12 --drift-threshold 0.20
```

Output is a per-class count summary plus the top N triggers by `|Δ|` (configurable via `--show`). Replays write to `alert_log` (with `suppressed` reason populated) but do not touch `alert_state`, so the live cooldown machine is unaffected.

## Adding / removing watchlist events

Edit `C:\IMDR_LOCAL\polymarket\watchlist.yml` directly — see [`watchlist_format.md`](watchlist_format.md) for schema. Both `streaming.py loop` and `polywatch.py loop` hot-reload the file on every cycle — no restart needed.

Polywatch will start firing on a newly-added event once `streaming.py` has logged ≥ 2 snapshots for it (need a "prior snapshot" to compute snapshot-over-snapshot Δ). For the rolling-window DRIFT class to fire, you need ≥ `drift_lookback_hours` of history (6h by default).

## Inspecting alert history

`alert_log` is append-only. A few queries that pay back:

```sql
-- What fired in the last 24 hours, by class.
SELECT alert_class, COUNT(*) AS n
FROM alert_log
WHERE alert_ts > datetime('now', '-1 day')
  AND suppressed IS NULL
GROUP BY alert_class
ORDER BY n DESC;

-- Full alert history for a specific event.
SELECT alert_ts, alert_class, modal_yes, prior_modal_yes, delta, vol_ratio, suppressed
FROM alert_log
WHERE event_id = ?
ORDER BY alert_ts DESC;

-- Suppressed-by-ILLIQUID rate per event — find watchlist entries to retire.
SELECT event_slug,
       COUNT(*) AS total,
       SUM(CASE WHEN suppressed = 'ILLIQUID' THEN 1 ELSE 0 END) AS illiquid,
       1.0 * SUM(CASE WHEN suppressed = 'ILLIQUID' THEN 1 ELSE 0 END) / COUNT(*) AS illiquid_share
FROM alert_log
GROUP BY event_slug
HAVING COUNT(*) > 5
ORDER BY illiquid_share DESC;
```

## Troubleshooting

**"No email arrived but I see triggers in stdout."**
Three checks, in order:
1. `settings.email_enabled` is True and `settings.email_to` is non-empty (`.env`, `IMDR_EMAIL_ENABLED=true`, `IMDR_EMAIL_TO=...`).
2. Outlook is open on the host (the sender uses `win32com` against a running Outlook session).
3. `alert_log` has rows for the cycle but they all have `suppressed` set — ILLIQUID and COOLDOWN both look like "no email" at the user level.

**"Alert spam during a single trending move."**
Raise `--cooldown-minutes` (e.g. 60), or raise `--rearm-delta` (e.g. 0.10) so each new email requires a larger further move from the last alert level. The defaults assume 15-minute polling — at faster intervals you may want a longer cooldown.

**"Too many ILLIQUID suppressions on an event I care about."**
The modal market on that event is genuinely illiquid (its dealer has wide quotes). Two options: remove the event from the watchlist, or raise `--illiquid-spread` (e.g. 0.30) — but raising the threshold globally lets in noise on other events too. Better to retire the event.

**"Detector logs `no snapshots in DB yet`."**
`streaming.py loop` isn't running, or hasn't completed its first poll yet. Check Terminal 1.

**"VOL_BURST never fires."**
Need ≥ 7 days of `volume_24h` history per modal market for the baseline median. New watchlist entries are below the floor for the first week.

## What's deferred

- **Teams channel alerts.** Step 3.5 in the buildout doc — design lives in [polymarket_buildout.md](polymarket_buildout.md). Email is sufficient for now.
- **Promotion of `alert_log` to MSSQL.** Tied to the broader Step 7 — only if cross-team access becomes a need.
