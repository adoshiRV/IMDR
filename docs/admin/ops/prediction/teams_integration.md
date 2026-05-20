# Polymarket → Teams Channel Integration

The Polymarket macro snapshot posts to a Teams channel twice a day as an
Adaptive Card. This is Step 3.5 of [polymarket_buildout.md](polymarket_buildout.md).

- **AM post** — fires inside `scripts/imdr_daily.py` at 08:00 SGT.
- **PM post** — fires from `scripts/imdr_evening.py` at 20:00 SGT (separate
  Task Scheduler entry — see below).

The card uses the same `SnapshotData` produced by the HTML snapshot, so the
Teams post and the canonical HTML at
`C:\IMDR_LOCAL\polymarket\snapshots\macro_snapshot_*.html` always reflect
the same `observations.db` state.

---

## 1. Create the Teams Workflow webhook (one-time, manual)

Microsoft retired Office 365 connectors in late 2024. The replacement is
the **Workflows** flow "Post to a channel when a webhook request is
received". It exposes the same HTTPS webhook surface; payload is an
Adaptive Card wrapped in `{type: "message", attachments: [...]}`.

Steps in Teams:

1. Open the target channel (e.g. `Macro / Prediction Markets`).
2. Click the channel **…** menu → **Workflows**.
3. Search **"Post to a channel when a webhook request is received"** and
   add it.
4. Sign in with the desk service / shared account if prompted. Confirm
   the team + channel target.
5. After the flow saves, copy the **HTTP POST URL** it generates. This is
   the webhook URL.

The flow is owned by whoever created it — if that person leaves the
tenant, the flow stops. Best practice: create it under a shared / service
account, not a personal one.

## 2. Configure the webhook URL

Add to your local `.env`:

```ini
IMDR_TEAMS_POLYMARKET_WEBHOOK=https://prod-XX.<region>.logic.azure.com:443/workflows/...
```

(See `.env.example` for the placeholder line.)

The setting is read via [`Settings.teams_polymarket_webhook`](../../../../src/imdr/config/settings.py).
If unset, `teams_post.py` no-ops with a log line — wiring it into the
schedulers is safe even before the URL exists.

## 3. Verify end-to-end

```powershell
python -m scripts.prediction.polymarket.teams_post --slot AM
```

Expected console output:

```
[teams_post] posted N rows to Teams channel.
```

Check the Teams channel — a card titled **"Polymarket Macro Snapshot — AM"**
should appear within seconds, with one row per watchlist event grouped by
section. Each row is a tappable link to its Polymarket event page.

If you only want to post without rewriting the local HTML artifact, add
`--skip-html`.

## 4. Schedule the PM run

The AM post is already registered in [imdr_daily.py](../../../../scripts/imdr_daily.py).
The PM post needs its own Windows Task Scheduler entry:

1. Open **Task Scheduler** → **Create Basic Task**.
2. Name: `IMDR Evening — Polymarket Teams PM`.
3. Trigger: **Daily**, start time **20:00**, recur every 1 day.
4. Action: **Start a program**.
   - Program: `C:\Users\adoshi\.conda\envs\imdr\python.exe`
   - Arguments: `-m scripts.imdr_evening`
   - Start in: `Z:\Business\Personnel\Arjun\GitHub\IMDR`
5. On the Settings tab: tick **Run task as soon as possible after a
   scheduled start is missed** so a laptop-asleep skip recovers.

Same pattern as the existing `IMDR Daily` task — copy that one and edit
the time + arguments if easier.

## 5. Card layout

The card is rendered by
[`src/imdr/notifications/formatters/macro_snapshot_card.py`](../../../../src/imdr/notifications/formatters/macro_snapshot_card.py).
For each watchlist event it shows:

| Column | Content |
| --- | --- |
| Asset pill | e.g. `USD`, `BRENT`, `EUR` |
| Event label + modal sub-market | wraps to 2 lines; subtitle has target date, 24h vol, horizon-mismatch warning when present |
| Outcome % + Δ24h | bolded percent in Accent colour; delta in Good (green) / Attention (red) / Default |

Tail sub-rows from the HTML snapshot are **dropped from the card** — the
desk's deep-dive flow is to click through to either the HTML or the
Polymarket event page. Keeps the payload comfortably under the ~28 KB
Adaptive Card limit on Workflows.

## 6. Troubleshooting

| Symptom | Cause / fix |
| --- | --- |
| `[teams_post] IMDR_TEAMS_POLYMARKET_WEBHOOK not configured — skipping.` | `.env` value is empty. Set it (Section 2). |
| `teams_post_rejected` in logs with status 400 | Card payload exceeded ~28 KB, or Adaptive Card schema invalid. Check the latest `data.rows` count; if the watchlist has grown large, consider tightening row caps in the formatter. |
| `teams_post_failed` with connection error | Network / Workflows URL down. The HTML snapshot still wrote — re-run the command later. |
| Card posts but rows look stale | `observations.db` hasn't been refreshed by `streaming.py`. Check the poller. |
| Flow stopped firing | Workflow owner left the tenant, or the flow's auth expired. Re-create under a shared account. |

## 7. Future / deferred

- **Polywatch SPIKE/MODAL_FLIP alerts** to Teams — the formatter pattern
  here is reusable: build a new card builder in
  `src/imdr/notifications/formatters/polywatch_card.py` and call
  `post_adaptive_card` against the same webhook (or a separate one for
  alerts-only).
- **SharePoint link to HTML** in the card — would need the HTML uploaded
  via the OneDrive-sync path
  ([`project_sharepoint_via_onedrive_sync.md`](../../../../docs/admin/ops/sharepoint.md)).
  Skipped for now to keep the integration self-contained.
