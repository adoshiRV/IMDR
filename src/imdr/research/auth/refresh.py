"""Verify + auto-relog orchestration.

``refresh(vendor)`` runs :func:`verify` and, on EXPIRED, attempts a
recovery appropriate to the vendor's :class:`AuthMode`:

* :data:`AuthMode.PROGRAMMATIC` — open the auth context (which runs
  ``loginflows.{vendor}.login`` as part of its setup); on success the
  next ``verify`` should land LIVE.
* :data:`AuthMode.PROFILE_ONLY` / :data:`AuthMode.HEADER_INJECTION` —
  cannot self-recover; return a NEEDS_HUMAN-flavoured outcome with
  the vendor's healthcheck URL so the operator knows where to SSO.

``refresh_all`` runs :func:`refresh` over every registered vendor (or
a caller-supplied subset) sequentially. Vendor crawlers each lock their
own profile dir while running, so parallelising is not worth the
race-condition risk for a heartbeat job.
"""
from __future__ import annotations

import time
from collections.abc import Iterable
from dataclasses import dataclass

from .context import get_authed_context
from .registry import AuthMode, all_vendors, get_spec
from .verify import SessionStatus, VerifyResult, verify


@dataclass(slots=True, frozen=True)
class RefreshOutcome:
    vendor: str
    before: SessionStatus
    after: SessionStatus
    elapsed_s: float
    needs_human: bool       # True when only a headed SSO can recover
    healthcheck_url: str
    detail: str = ""

    @property
    def recovered(self) -> bool:
        return self.before != SessionStatus.LIVE and self.after == SessionStatus.LIVE


async def _attempt_programmatic_recovery(vendor: str) -> VerifyResult:
    """Open + close an auth context — that triggers the login flow as
    part of setup. Then re-verify.
    """
    try:
        async with get_authed_context(vendor) as _ctx:
            pass  # login happens during __aenter__
    except Exception as exc:
        return VerifyResult(
            vendor=vendor,
            status=SessionStatus.EXPIRED,
            detail=f"login failed: {type(exc).__name__}: {exc!s:.300}",
        )
    return await verify(vendor)


async def refresh(vendor: str) -> RefreshOutcome:
    """Verify + (where possible) recover one vendor's session."""
    started = time.perf_counter()
    spec = get_spec(vendor)
    before = await verify(vendor)

    if before.status == SessionStatus.LIVE:
        return RefreshOutcome(
            vendor=vendor,
            before=before.status,
            after=before.status,
            elapsed_s=time.perf_counter() - started,
            needs_human=False,
            healthcheck_url=spec.healthcheck_url,
            detail=before.detail,
        )

    if spec.mode == AuthMode.PROGRAMMATIC:
        after = await _attempt_programmatic_recovery(vendor)
        return RefreshOutcome(
            vendor=vendor,
            before=before.status,
            after=after.status,
            elapsed_s=time.perf_counter() - started,
            needs_human=after.status != SessionStatus.LIVE,
            healthcheck_url=spec.healthcheck_url,
            detail=after.detail or before.detail,
        )

    # PROFILE_ONLY / HEADER_INJECTION — cannot self-recover.
    return RefreshOutcome(
        vendor=vendor,
        before=before.status,
        after=before.status,
        elapsed_s=time.perf_counter() - started,
        needs_human=True,
        healthcheck_url=spec.healthcheck_url,
        detail=before.detail or (
            f"SSO-only vendor — run "
            f"`python -m imdr.research.auth login --vendor {vendor}` "
            f"and complete SSO in headed Chrome."
        ),
    )


async def refresh_all(
    vendors: Iterable[str] | None = None,
) -> list[RefreshOutcome]:
    """Refresh every vendor (or the supplied subset). Sequential."""
    targets = tuple(vendors) if vendors is not None else all_vendors()
    out: list[RefreshOutcome] = []
    for v in targets:
        out.append(await refresh(v))
    return out


__all__ = ["RefreshOutcome", "refresh", "refresh_all"]
