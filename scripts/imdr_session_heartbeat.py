"""Pre-emptive research-vendor session refresh.

Runs ``imdr.research.auth.refresh_all`` once and emits a single-line
summary to stdout, suitable for piping into a cron / Task Scheduler
job. The goal: catch expired SSO cookies hours BEFORE the daily
``playground/research/ingest_today.py`` run, so:

* Programmatic vendors (Barclays) auto-recover silently.
* SSO-only vendors surface a NEEDS_HUMAN line the operator can act on
  before the next dispatch window. When any vendor is in NEEDS_HUMAN,
  an operator email is dispatched (subject to ``IMDR_EMAIL_ENABLED``
  + a configured recipient; suppressible via ``--no-email``).

**Not wired into a scheduler.** Per the project rule
[feedback_no_prod_wiring_without_permission], this script is built
ready-to-run but NOT registered in ``scripts/imdr_hourly.py`` or
``scripts/imdr_daily.py`` yet. To opt in, add::

    ["python", "-m", "scripts.imdr_session_heartbeat"]

to the PIPELINES list of whichever scheduler should own it.

Exit codes
----------
* ``0`` — every vendor is LIVE (post-refresh).
* ``2`` — one or more vendors need human re-auth (SSO-only EXPIRED).
* ``1`` — unexpected error.

Usage
-----
    python -m scripts.imdr_session_heartbeat              # all vendors
    python -m scripts.imdr_session_heartbeat --vendor jpm
    python -m scripts.imdr_session_heartbeat --vendor anz,socgen
    python -m scripts.imdr_session_heartbeat --no-email   # suppress email
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import datetime, timezone

from imdr.research.auth import refresh_all
from imdr.research.auth.registry import VENDOR_AUTH_REGISTRY, all_vendors


def _resolve_vendors(arg: str | None) -> tuple[str, ...]:
    if not arg or arg.lower() == "all":
        return all_vendors()
    out = tuple(v.strip().lower() for v in arg.split(",") if v.strip())
    bad = [v for v in out if v not in VENDOR_AUTH_REGISTRY]
    if bad:
        raise SystemExit(
            f"unknown vendor(s): {', '.join(bad)}; "
            f"known: {', '.join(all_vendors())}"
        )
    return out


async def _run(vendors: tuple[str, ...], *, send_email: bool) -> int:
    outcomes = await refresh_all(vendors)
    n_live = sum(1 for o in outcomes if o.after.value == "live")
    n_recovered = sum(1 for o in outcomes if o.recovered)
    needs_human = [o for o in outcomes if o.needs_human]
    ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    print(
        f"[{ts}] session-heartbeat: "
        f"{n_live}/{len(outcomes)} live, "
        f"{n_recovered} recovered, "
        f"{len(needs_human)} need human"
    )
    for o in needs_human:
        print(f"  NEEDS_HUMAN  {o.vendor:<10}  {o.healthcheck_url}")
        if o.detail:
            print(f"               {o.detail[:200]}")

    # Operator email — only fires when at least one vendor needs a
    # human and the caller hasn't opted out. send_auth_email() itself
    # respects Settings.email_enabled + recipient configuration, so
    # silenced environments are silent regardless.
    if send_email and needs_human:
        try:
            from imdr.research.auth.notify import send_auth_email  # noqa: PLC0415
            from imdr.research.auth.registry import get_spec  # noqa: PLC0415

            payload = []
            for o in needs_human:
                spec = get_spec(o.vendor)
                payload.append({
                    "vendor": o.vendor,
                    "mode": spec.mode.value,
                    "healthcheck_url": o.healthcheck_url,
                    "detail": o.detail or f"status={o.after.value}",
                })
            sent = send_auth_email(kind="needs_human", outcomes=payload)
            if sent:
                print("  [email] needs_human dispatched")
        except Exception as exc:  # noqa: BLE001 — email is side-effect
            print(f"  [email] dispatch raised (ignored): {type(exc).__name__}: {exc}")

    return 0 if not needs_human else 2


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m scripts.imdr_session_heartbeat",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--vendor", default=None,
        help='vendor code, comma-list, or "all" (default: all)',
    )
    parser.add_argument(
        "--no-email", action="store_true",
        help="suppress the NEEDS_HUMAN operator email",
    )
    args = parser.parse_args(argv)
    return asyncio.run(
        _run(_resolve_vendors(args.vendor), send_email=not args.no_email),
    )


if __name__ == "__main__":
    sys.exit(main())
