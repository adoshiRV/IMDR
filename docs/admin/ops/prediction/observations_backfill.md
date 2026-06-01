# Polymarket observations backfill

> Keywords: polymarket backfill, polymarkets backfill, observations.db backfill,
> price-history backfill, CLOB prices-history, warm-up backfill, new-slug
> backfill, watchlist backfill.

`scripts/prediction/polymarket/backfill.py` warms `C:\IMDR_LOCAL\polymarket\observations.db`
with the last N hours of YES-price history for any active watchlist slug that
has insufficient prior context. Polled by hand when a slug is freshly added
to `watchlist.yml` so polywatch's DRIFT / VOL_BURST checks have a baseline to
fire against.

**Not to be confused with** `polywatch backfill` (a polywatch.py subcommand
that *replays detection logic* over already-stored observations for threshold
tuning — see [polywatch_operations.md](polywatch_operations.md)).

## When to run

- After adding new concrete (non-wildcard) slugs to `watchlist.yml`.
- After replacing a wildcard slug with its concrete counterpart (Polymarket
  posts the event late, e.g. `may-inflation-us-monthly-*` → `may-inflation-us-monthly`).
- Default check: every active concrete slug needs ≥48h of history to be
  considered "warm" — the script auto-detects which ones lack it.

## Commands

```powershell
# Auto-detect slugs needing backfill, default 48h, fidelity 15 min
python -m scripts.prediction.polymarket.backfill

# Custom horizon
python -m scripts.prediction.polymarket.backfill --hours 72

# Specific slugs
python -m scripts.prediction.polymarket.backfill --slugs slug1 slug2
```

Source: CLOB `/prices-history` per sub-market `clobTokenIds[0]` (YES token).
Idempotent via `INSERT OR IGNORE`. Backfilled rows have NULL for spread / bid /
ask / volume / liquidity — CLOB history only returns (t, p). Polywatch's
SPIKE / MODAL_FLIP / DRIFT checks all work on `yes_price` alone; VOL_BURST is
naturally skipped on rows with NULL volume.

## Always poll after backfilling

Backfill writes rows with historical timestamps. The script bounds `end_ts`
strictly below both (a) the slug's earliest existing live row and (b) the
global `MAX(snapshot_ts)` in `market_observation` (fix landed
2026-06-01) so a backfill point can never become the new MAX and pollute
[macro_snapshot.py](../../../../scripts/prediction/polymarket/macro_snapshot.py)'s
`SELECT MAX(snapshot_ts)` lookup.

Even so, the recommended order of operations after edits to `watchlist.yml`
is:

```powershell
python -m scripts.prediction.polymarket.streaming poll      # current snapshot
python -m scripts.prediction.polymarket.backfill            # historical warm-up
python -m scripts.prediction.polymarket.streaming poll      # re-stamp MAX
python -m scripts.prediction.polymarket.macro_snapshot      # render
```

The trailing poll guarantees a fresh MAX snapshot_ts spans every slug, so the
snapshot binds all watchlist rows. Without it, slugs whose only rows are from
backfill (older timestamps) will surface as `missing` in the snapshot output
because `latest_ts` lookup misses them.

## Historical incident (2026-06-01)

After replacing 4 stale May-data wildcards with concrete slugs in
`watchlist.yml` and running backfill, `macro_snapshot` reported 53 missing
labels. Root cause: `end_ts = now − 60s` for genuinely-new slugs landed past
the most recent live-poll timestamp (12:16) at ~12:19, becoming the new global
MAX. Only the 33 markets backfilled at that exact instant had rows at MAX, so
every other watchlist entry failed the `event_slug = ? AND snapshot_ts = MAX`
join. Fix: cap `end_ts < global MAX(snapshot_ts) − 1s`. A fresh poll then
restored the correct invariant. See
[backfill.py:127-148](../../../../scripts/prediction/polymarket/backfill.py).

## Output

```
[backfill] 9 watchlist slugs lack 48h of history
  how-many-jobs-added-in-may-945     markets=6   rows=1158  ok
  may-inflation-us-annual            markets=12  rows=2316  ok
  ...
[backfill] done — 9 slugs, 67 live markets, 12931 rows inserted (INSERT OR IGNORE).
```

## Related

- [watchlist_format.md](watchlist_format.md) — `watchlist.yml` schema.
- [polymarket_buildout.md](polymarket_buildout.md) — overall architecture.
- [polywatch_operations.md](polywatch_operations.md) — distinguishes `polywatch backfill`
  (detection replay) from this script (observation warm-up).
- [macro_snapshot.md](macro_snapshot.md) — consumer that breaks when backfill
  rows overtake live polls.
