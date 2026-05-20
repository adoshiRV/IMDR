"""Post the Polymarket macro snapshot to a Teams channel.

Reads the latest snapshot from `observations.db`, also writes the canonical
HTML artifact (so the HTML pipeline isn't a parallel path that can drift),
then renders an Adaptive Card and POSTs to the Teams Workflows webhook
configured at `IMDR_TEAMS_POLYMARKET_WEBHOOK`.

Run:
    python -m scripts.prediction.polymarket.teams_post --slot AM
    python -m scripts.prediction.polymarket.teams_post --slot PM

If the webhook is unset, the command logs and exits 0 (no-op) so it can be
wired into schedulers without breaking pre-config environments.

See `docs/admin/ops/prediction/teams_integration.md` for the one-time
Workflows setup.
"""

from __future__ import annotations

import argparse
import sys

from imdr.config.settings import get_settings
from imdr.notifications.formatters.macro_snapshot_card import build_cards
from imdr.notifications.teams import post_adaptive_card
from scripts.prediction.polymarket.macro_snapshot import (
    build_snapshot,
    collect_snapshot_rows,
)


for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass


def main() -> int:
    ap = argparse.ArgumentParser(prog="teams_post")
    ap.add_argument("--slot", choices=("AM", "PM"), default="",
                    help="Optional time-of-day suffix appended to the card title.")
    ap.add_argument("--skip-html", action="store_true",
                    help="Skip writing the HTML artifact (Teams-only post).")
    args = ap.parse_args()

    settings = get_settings()
    webhook = settings.teams_polymarket_webhook.strip()
    if not webhook:
        print("[teams_post] IMDR_TEAMS_POLYMARKET_WEBHOOK not configured — skipping.")
        return 0

    data = collect_snapshot_rows()
    if not args.skip_html:
        # Keep the HTML artifact in lockstep with the Teams post so the
        # canonical full-detail file always reflects the same snapshot
        # the channel just saw.
        try:
            build_snapshot()
        except Exception as exc:  # noqa: BLE001
            print(f"[teams_post] HTML write failed (continuing): {exc}")

    title_suffix = f" — {args.slot}" if args.slot else ""
    cards = build_cards(
        rows=data.rows,
        snapshot_ts=data.snapshot_ts,
        generated_ts=data.generated_ts,
        missing=data.missing,
        dropped_stale=data.dropped_stale,
        title_suffix=title_suffix,
    )

    failed = 0
    for i, card in enumerate(cards, start=1):
        if not post_adaptive_card(webhook, card):
            print(f"[teams_post] post {i}/{len(cards)} failed.")
            failed += 1
    if failed:
        return 1
    print(
        f"[teams_post] posted {len(data.rows)} rows across {len(cards)} card(s)."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
