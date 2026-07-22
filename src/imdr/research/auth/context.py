"""Async context manager that hands a crawler a ready BrowserContext.

Replaces the open-coded ``launch_persistent_context`` block that used
to live in every vendor crawler. Responsibilities:

1. Wipe the profile dir for vendors that require it (Barclays).
2. Launch persistent Chrome with vendor-specific headless / downloads
   flags.
3. Inject extra HTTP headers (JPM ``janus_user``).
4. Run a programmatic login when the registry says so.
5. Snapshot ``storage_state`` to JSON on exit (best-effort).
6. Close the context cleanly.

On login failure (``LoginFailedError`` / ``CredentialMissing``), this
module fires the ``login_failed`` operator email before re-raising —
controlled by ``IMDR_RESEARCH_AUTH_EMAIL_ON_AUTH_FAILURE`` (default
on). The validate CLI sets the flag to ``false`` for its own context
calls so it doesn't double-email.

Usage::

    async with get_authed_context("barclays") as ctx:
        page = await ctx.new_page()
        ...
"""
from __future__ import annotations

import importlib
import os
import types
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from ._paths import profile_dir
from .errors import AuthError, CredentialMissing
from .registry import AuthMode, VendorAuthSpec, get_spec
from .state import snapshot as state_snapshot

# Settings field names per vendor. Centralised so adding a new
# PROGRAMMATIC vendor is a one-line change. Barclays uses the legacy
# ``barclays_*`` field name (env var ``IMDR_BARCLAYS_*``); everyone else
# follows the ``research_{vendor}_*`` convention (``IMDR_RESEARCH_{V}_*``).
_CRED_FIELDS: dict[str, tuple[str, str, str]] = {
    # vendor -> (username_field, password_field, env_var_prefix)
    "barclays": ("barclays_username", "barclays_password", "IMDR_BARCLAYS"),
    "ubs": ("research_ubs_username", "research_ubs_password", "IMDR_RESEARCH_UBS"),
    "anz": ("research_anz_username", "research_anz_password", "IMDR_RESEARCH_ANZ"),
    "nomura": (
        "research_nomura_username", "research_nomura_password",
        "IMDR_RESEARCH_NOMURA",
    ),
    "stanc": (
        "research_stanc_username", "research_stanc_password",
        "IMDR_RESEARCH_STANC",
    ),
    # DB has no password — the "secret" is a code emailed on submit.
    # An empty pass_field tells _run_programmatic_login to skip the
    # password-presence check below.
    "db": ("research_db_username", "", "IMDR_RESEARCH_DB"),
}

_EMAIL_ON_FAILURE_ENV = "IMDR_RESEARCH_AUTH_EMAIL_ON_AUTH_FAILURE"


def _email_on_failure_enabled() -> bool:
    """Read the env flag. Default True (so daily orchestrators alert on
    auth breakage without any wiring). validate/tests set ``false``.
    """
    raw = os.environ.get(_EMAIL_ON_FAILURE_ENV, "true").strip().lower()
    return raw not in {"0", "false", "no", "off", ""}


def _maybe_emit_login_failure_email(spec: VendorAuthSpec, exc: BaseException) -> None:
    """Fire a ``login_failed`` email; never raise.

    Best-effort — wrapped in a broad except so a malformed Settings or
    a missing Outlook install cannot break the auth path. The original
    auth exception always takes priority.
    """
    if not _email_on_failure_enabled():
        return
    try:
        # Late import keeps the notify module out of the cold-import path
        # for callers that don't trigger an email.
        from .notify import send_auth_email

        send_auth_email(
            kind="login_failed",
            vendor=spec.code,
            mode=spec.mode.value,
            healthcheck_url=spec.healthcheck_url,
            error_type=type(exc).__name__,
            error_message=str(exc)[:500],
            recoverable=getattr(exc, "recoverable", False),
            mfa_kind=getattr(exc, "mfa_kind", ""),
        )
    except Exception:
        pass


def _ensure_clean_profile(vendor: str) -> None:
    """Wipe the profile dir; used for ``wipe_profile_per_run=True``."""
    import shutil

    p = profile_dir(vendor)
    if p.exists():
        shutil.rmtree(p, ignore_errors=True)
    p.mkdir(parents=True, exist_ok=True)


def _load_loginflow(spec: VendorAuthSpec) -> types.ModuleType:
    if not spec.login_module:
        # This is a registry-shape bug, not an auth failure — surface
        # via plain RuntimeError so callers don't catch it as AuthError.
        raise RuntimeError(
            f"vendor {spec.code!r} has mode={spec.mode.value} but no "
            f"login_module configured in registry"
        )
    return importlib.import_module(spec.login_module)


async def _run_programmatic_login(ctx, spec: VendorAuthSpec) -> None:
    """Dispatch to ``loginflows.{vendor}.login`` with credentials from
    :class:`Settings`. Idempotent — the loginflow's own
    ``is_authenticated`` short-circuits when cookies are already live.

    Raises:
        CredentialMissing: when the cred-map lookup fails or either of
            the username/password fields is empty.
        LoginFailedError: re-raised from the loginflow when the form
            submit lands back on the login page.
    """
    from imdr.config.settings import get_settings

    settings = get_settings()

    fields = _CRED_FIELDS.get(spec.code)
    if fields is None:
        # Registry-shape bug, not a user-actionable cred problem.
        raise RuntimeError(
            f"no credential mapping for vendor {spec.code!r} — extend "
            f"context._CRED_FIELDS"
        )
    user_field, pass_field, env_prefix = fields
    username = getattr(settings, user_field, "") or ""
    # An empty pass_field (e.g. db) means the vendor has no password —
    # the login secret is a one-time code, not a Settings field.
    password = (getattr(settings, pass_field, "") or "") if pass_field else ""
    if not username or (pass_field and not password):
        raise CredentialMissing(
            f"{spec.code.upper()} credentials missing — set "
            f"{env_prefix}_USERNAME"
            f"{' / _PASSWORD' if pass_field else ''} in .env",
            vendor=spec.code,
            env_var_prefix=env_prefix,
        )
    flow = _load_loginflow(spec)
    await flow.login(ctx, username=username, password=password)


@asynccontextmanager
async def get_authed_context(
    vendor: str,
    *,
    headless: bool | None = None,
    accept_downloads: bool | None = None,
    wipe_profile: bool | None = None,
) -> AsyncIterator:
    """Yield a Playwright ``BrowserContext`` authenticated as ``vendor``.

    Parameters
    ----------
    vendor
        Registry key (e.g. ``"barclays"``, ``"jpm"``).
    headless
        Override the spec default — useful for the headed
        ``login --vendor X`` CLI subcommand.
    accept_downloads
        Override the spec default. Most crawlers don't trigger
        downloads (PDFs are fetched via direct GET), but BofA's
        per-resource POST handshake needs it.
    wipe_profile
        Override ``spec.wipe_profile_per_run``. Use ``False`` for the
        second of two back-to-back entries in the same run (e.g.
        Barclays' ``fetch_pdfs`` reusing the session that
        ``discover_reports`` just established).

    The yielded context already has any registry-configured
    ``extra_http_headers`` applied and, for ``PROGRAMMATIC`` vendors,
    has been re-logged when stale. The crawler should treat it as
    "ready to use".

    On :class:`AuthError` during setup (login failure, missing creds),
    fires the ``login_failed`` operator email (env-gated) before
    re-raising. Snapshot + close always run regardless of outcome.
    """
    from playwright.async_api import async_playwright

    spec = get_spec(vendor)

    should_wipe = spec.wipe_profile_per_run if wipe_profile is None else wipe_profile
    if should_wipe:
        _ensure_clean_profile(vendor)

    async with async_playwright() as pw:
        ctx = await pw.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir(vendor)),
            channel="chrome",
            headless=spec.headless if headless is None else headless,
            accept_downloads=(
                spec.accept_downloads
                if accept_downloads is None
                else accept_downloads
            ),
        )
        try:
            if spec.extra_headers_factory is not None:
                headers = spec.extra_headers_factory()
                if headers:
                    await ctx.set_extra_http_headers(headers)

            if spec.mode == AuthMode.PROGRAMMATIC:
                try:
                    await _run_programmatic_login(ctx, spec)
                except AuthError as exc:
                    _maybe_emit_login_failure_email(spec, exc)
                    raise

            yield ctx
        finally:
            # Snapshot first, then close. Reverse order would race
            # ``ctx.close()`` and ``ctx.storage_state()``.
            from .loginflows._base import silent_cleanup

            try:
                await state_snapshot(ctx, vendor)
            finally:
                async with silent_cleanup("context.get_authed_context.ctx.close"):
                    await ctx.close()


__all__ = ["get_authed_context"]
