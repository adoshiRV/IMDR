# Polymarket watchlist format

Single source of truth for everything the IMDR Polymarket stack does:

- **`scripts/prediction/polymarket/streaming.py`** decides which slugs to poll.
- **`scripts/prediction/polymarket/polywatch.py`** groups alert emails by `asset_tag`.
- **`scripts/prediction/polymarket/macro_snapshot.py`** renders curated snapshot rows.

File: `C:\IMDR_LOCAL\polymarket\watchlist.yml` (lives outside the repo —
operational config, not source-controlled).
Loader: [`scripts/prediction/polymarket/watchlist.py`](../../scripts/prediction/polymarket/watchlist.py).

## Schema

```yaml
events:
  - slug: ecb-decision-in-june          # required
    asset_tag: g10_cb                    # required
    section: Europe / G10 CB             # snapshot-only (optional)
    label: ECB June 2026 decision        # snapshot-only
    asset: EUR                           # snapshot-only (asset pill text)
    market_read: "25bp cut fully priced; risk is skip or 50bp surprise."
    event_date: 2026-06-04               # ISO date
    event_id: 287227                     # optional — direct DB lookup
    pruned: false                        # set by `streaming prune --apply`
    pruned_at: null                      # ISO date when pruned
    pruned_reason: null                  # MISSING | DEAD | ERROR
```

### Field reference

| Field | Required | Type | Notes |
|---|---|---|---|
| `slug` | ✅ | str | `^[a-z0-9][a-z0-9-]*\*?$`. Trailing `*` enables prefix match in macro_snapshot for events Polymarket hasn't posted yet. |
| `asset_tag` | ✅ | str | `^[a-z0-9_]+$`. Drives polywatch email grouping. Display order set by `ASSET_TAG_ORDER` in [`polywatch.py`](../../scripts/prediction/polymarket/polywatch.py); unlisted tags render alphabetically after. |
| `section` | for snapshot | str | Heading group in macro_snapshot. Listed in `SECTION_ORDER`. |
| `label` | for snapshot | str | Row label. |
| `asset` | for snapshot | str | Pill text (e.g. `EUR`, `USD/Tariff`, `Oil`). |
| `market_read` | for snapshot | str | Editorial commentary. |
| `event_date` | optional | ISO date | Release / decision / resolution date. Drives upcoming-vs-resolved classification. Omit for open-ended events. |
| `event_id` | optional | int | Polymarket numeric event ID. Preferred over slug for lookup. |
| `pruned` | optional | bool | Filtered out at load when `true`. Managed by `streaming prune --apply`. |
| `pruned_at` | optional | ISO date | When pruned. |
| `pruned_reason` | optional | str | One of `MISSING`, `DEAD`, `ERROR`. |

### Wildcard slugs

A slug ending in `*` is **prefix-matched** by macro_snapshot against
`event_slug` in `observations.db` — useful for forward-looking events
Polymarket hasn't posted yet:

```yaml
- slug: how-many-jobs-added-in-may-*
  asset_tag: us_data
  section: US Data & Fed
  label: May Nonfarm Payrolls
  asset: US jobs
  event_date: 2026-06-05
  market_read: "Prints Fri Jun 5; first read on tariff-shock pass-through."
```

Polling consumers (`streaming.py`, `polywatch.py`) **skip** wildcard entries —
auto-discovery picks them up once Polymarket posts the concrete slug.

### Editorial vs polling-only entries

A bare entry with just `slug` + `asset_tag` is valid and gets streamed +
polywatched, but won't render in the snapshot:

```yaml
- slug: trump-announces-us-blockade-of-hormuz-lifted-by
  asset_tag: oil_mena
```

## Curation principle

Only **information-flow event-resolution markets** that historically front-run
a specific asset move. Excluded:

- Asset-price binaries (BTC/ETH/WTI hits, commodity-future targets) — they
  trail spot, not lead it.
- 2028 nominee speculation, state/provincial elections, sports/entertainment.
- Local US ballot props, individual-district House races.

Detailed exclusion regex lives in `CURATION_EXCLUDE_PATTERNS` in
[`streaming.py`](../../scripts/prediction/polymarket/streaming.py); that filter
applies to **auto-discovered** slugs but the manual watchlist always polls.

## Operational lifecycle

### Adding an event

1. Add an `events:` entry to `watchlist.yml` with at least `slug` + `asset_tag`.
2. Add `section`, `label`, `asset`, `market_read`, `event_date` to surface it in
   the macro snapshot.
3. Streaming picks it up on the next poll cycle (no restart needed).

### Pruning dead/missing slugs

```bash
# Dry-run audit
python -m scripts.prediction.polymarket.streaming prune

# Apply: flips `pruned: true` on dead/missing entries (with .bak)
python -m scripts.prediction.polymarket.streaming prune --apply
```

The daily cron in [`scripts/imdr_daily.py`](../../scripts/imdr_daily.py)
runs `prune --apply` automatically. Pruned entries stay in the YAML for
audit history but are filtered out at load time. To re-enable a pruned entry,
manually flip `pruned: false` (or delete the field).

**Caveat**: `mark_pruned` round-trips via PyYAML, which does **not** preserve
comments. If you maintain comments inline, expect them to be wiped after the
first prune cycle. Put guidance in this doc instead.

### Validation

The loader rejects malformed entries at load time:

- Bad slug (`Foo Bar!`) → `WatchlistError: invalid slug`
- Bad asset_tag (`BAD-TAG`) → `WatchlistError: invalid asset_tag`
- Duplicate slug → `WatchlistError: duplicate slug`
- Invalid `pruned_reason` → `WatchlistError: pruned_reason must be one of...`
- Non-int `event_id` → `WatchlistError: event_id must be int`

Tests: [`tests/unit/test_polymarket_watchlist.py`](../../tests/unit/test_polymarket_watchlist.py).
