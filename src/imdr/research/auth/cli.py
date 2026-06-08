"""Operator CLI for research-portal session management.

Usage::

    python -m imdr.research.auth check                # verify all
    python -m imdr.research.auth check --vendor jpm
    python -m imdr.research.auth refresh              # verify + auto-relog
    python -m imdr.research.auth refresh --vendor barclays
    python -m imdr.research.auth login --vendor anz   # headed SSO seed
    python -m imdr.research.auth status               # snapshot timestamps
    python -m imdr.research.auth validate --vendor all  # full 5-step smoke

``check`` is read-only — it never wipes profiles or runs a login.
``refresh`` invokes :func:`refresh_all` and may wipe Barclays' profile
en route. ``login`` opens headed Chrome on the vendor's healthcheck URL
and polls until the predicate flips to LIVE — used to seed a new
profile or recover an SSO-only vendor. ``validate`` runs the full 5-step
end-to-end smoke (login -> snapshot -> discover -> fetch one PDF -> delete).

End-of-run summary emails fire after ``validate --vendor all`` unless
``--no-email`` is passed (or ``IMDR_EMAIL_ENABLED`` is False). The per-
vendor case is silent because the operator is watching the terminal.
"""
from __future__ import annotations

import argparse
import asyncio
import importlib
import os
import sys
import tempfile
import time
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from ._paths import snapshot_path
from .errors import AuthError, CredentialMissing, PDFValidationError
from .refresh import RefreshOutcome, refresh_all
from .registry import VENDOR_AUTH_REGISTRY, all_vendors, get_spec
from .verify import SessionStatus, VerifyResult, verify

# ---------------------------------------------------------------------
# Per-vendor metadata used by step 2 of validate
# ---------------------------------------------------------------------

# Vendor → Settings field name pair (username, password). Mirrors
# context._CRED_FIELDS but keeps the password slot empty for
# header-injection vendors so step 2 can render an accurate gap line.
_CRED_FIELDS: dict[str, tuple[str, str]] = {
    "barclays": ("barclays_username", "barclays_password"),
    "ubs": ("research_ubs_username", "research_ubs_password"),
    "anz": ("research_anz_username", "research_anz_password"),
    "nomura": ("research_nomura_username", "research_nomura_password"),
    "stanc": ("research_stanc_username", "research_stanc_password"),
    "jpm": ("research_jpm_username", ""),
}

# Vendor → expected MFA kind when validate surfaces a login gate. Used
# only for the step-2 "deferred — MFA risk: <kind>" hint line.
_DEFERRED_MFA: dict[str, str] = {
    "goldman": "mobile push",
    "hsbc": "hardware token",
    "jpm": "biometric push",
    "ms": "needs selector discovery; dual credential",
    "socgen": "SG Connect biometric",
    "westpac": "device-trust",
}

_STATUS_GLYPHS = {
    SessionStatus.LIVE: "OK ",
    SessionStatus.EXPIRED: "EXP",
    SessionStatus.NO_PROFILE: "NEW",
    SessionStatus.UNREACHABLE: "ERR",
}


# ---------------------------------------------------------------------
# CLI helpers
# ---------------------------------------------------------------------

def _resolve_vendors(arg: str | None) -> tuple[str, ...]:
    """``None`` / ``"all"`` → every registered vendor; comma-list otherwise."""
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


def _print_verify_row(r: VerifyResult) -> None:
    glyph = _STATUS_GLYPHS.get(r.status, "?  ")
    print(f"  {glyph}  {r.vendor:<10}  {r.url[:60]:<60}  {r.detail[:80]}")


def _print_refresh_row(o: RefreshOutcome) -> None:
    glyph = _STATUS_GLYPHS.get(o.after, "?  ")
    arrow = f"{o.before.value} -> {o.after.value}"
    flag = "  [needs human]" if o.needs_human else ""
    print(
        f"  {glyph}  {o.vendor:<10}  {arrow:<28}  "
        f"{o.elapsed_s:5.1f}s{flag}"
    )
    if o.needs_human and o.healthcheck_url:
        print(f"        → open {o.healthcheck_url}")
    if o.detail:
        print(f"        {o.detail[:200]}")


# ---------------------------------------------------------------------
# check / refresh / login / status
# ---------------------------------------------------------------------

async def _cmd_check(args: argparse.Namespace) -> int:
    vendors = _resolve_vendors(args.vendor)
    print(f"check: {len(vendors)} vendor(s)\n")
    n_bad = 0
    for v in vendors:
        r = await verify(v)
        _print_verify_row(r)
        if r.status != SessionStatus.LIVE:
            n_bad += 1
    print()
    print(f"summary: {len(vendors) - n_bad}/{len(vendors)} live")
    return 0 if n_bad == 0 else 1


async def _cmd_refresh(args: argparse.Namespace) -> int:
    vendors = _resolve_vendors(args.vendor)
    print(f"refresh: {len(vendors)} vendor(s)\n")
    outcomes = await refresh_all(vendors)
    n_human = 0
    n_recovered = 0
    for o in outcomes:
        _print_refresh_row(o)
        if o.needs_human:
            n_human += 1
        if o.recovered:
            n_recovered += 1
    print()
    print(
        f"summary: {len(vendors) - n_human}/{len(vendors)} live, "
        f"{n_recovered} recovered, {n_human} need human"
    )
    return 0 if n_human == 0 else 2


async def _cmd_login(args: argparse.Namespace) -> int:
    """Headed-Chrome SSO-seed for one vendor.

    Opens the vendor's healthcheck URL in a visible Chrome, waits for
    the human to complete SSO, polls the predicate every 2s. Saves a
    storage_state snapshot once live.
    """
    if not args.vendor or args.vendor.lower() == "all":
        raise SystemExit("login requires --vendor <code> (one at a time)")
    vendor = args.vendor.lower()
    spec = get_spec(vendor)

    print(f"login: {vendor}")
    print(f"  opening headed Chrome on {spec.healthcheck_url}")
    print("  complete SSO in the window; this CLI will poll every 2s.")

    from playwright.async_api import async_playwright

    from ._paths import profile_dir
    from .state import snapshot as state_snapshot

    async with async_playwright() as pw:
        ctx = await pw.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir(vendor)),
            channel="chrome",
            headless=False,            # human-visible — point of this command
            accept_downloads=False,
        )
        try:
            if spec.extra_headers_factory is not None:
                headers = spec.extra_headers_factory()
                if headers:
                    await ctx.set_extra_http_headers(headers)
            page = await ctx.new_page()
            await page.goto(spec.healthcheck_url, wait_until="domcontentloaded")
            deadline = time.monotonic() + 600  # 10-minute cap
            while time.monotonic() < deadline:
                try:
                    title = (await page.title()) or ""
                except Exception:
                    title = ""
                try:
                    url = page.url or ""
                except Exception:
                    url = ""
                if spec.healthcheck_predicate(title, url):
                    print(f"  [OK] live: {url}")
                    await state_snapshot(ctx, vendor)
                    return 0
                await asyncio.sleep(2.0)
            print("  [TIMEOUT] no LIVE signal within 10 minutes")
            return 3
        finally:
            from .loginflows._base import silent_cleanup
            async with silent_cleanup("cli._cmd_login.ctx.close"):
                await ctx.close()


def _cmd_status(args: argparse.Namespace) -> int:
    vendors = _resolve_vendors(args.vendor)
    print(f"status: {len(vendors)} vendor(s)\n")
    for v in vendors:
        p = snapshot_path(v)
        if p.exists():
            mtime = datetime.fromtimestamp(p.stat().st_mtime, tz=UTC)
            size_kb = p.stat().st_size / 1024
            print(
                f"  {v:<10}  snapshot {mtime.isoformat(timespec='seconds')}  "
                f"{size_kb:6.1f} KB  {p}"
            )
        else:
            print(f"  {v:<10}  (no snapshot yet)")
    return 0


# ---------------------------------------------------------------------
# validate — full 5-step per-vendor smoke
# ---------------------------------------------------------------------


@dataclass(slots=True, frozen=True)
class _OutcomeRecord:
    """Structured per-vendor validate result. Used both for the
    in-terminal summary and for the end-of-run email payload."""

    vendor: str
    rc: int
    mode: str
    status: str
    smoke: str           # "PASS" or "BLOCKED"
    elapsed_s: float
    reason: str          # empty on PASS; populated on BLOCKED

    def as_dict(self) -> dict[str, object]:
        return {
            "vendor": self.vendor,
            "mode": self.mode,
            "status": self.status,
            "smoke": self.smoke,
            "elapsed_s": self.elapsed_s,
            "reason": self.reason,
        }


def _step2_lines(vendor: str, spec) -> tuple[str, str, str]:
    """Return (current, could_be, gap) lines for validate step 2.

    Settings introspection is best-effort — if Settings import fails
    (e.g. .env malformed) we report "?" rather than crash the whole
    validate run.
    """
    from imdr.config.settings import get_settings

    try:
        settings = get_settings()
    except Exception as exc:
        return (
            f"current={spec.mode.value}",
            "could_be=?",
            f"gap=settings_read_failed: {type(exc).__name__}",
        )

    user_field, pass_field = _CRED_FIELDS.get(vendor, ("", ""))
    user_set = bool(getattr(settings, user_field, "").strip()) if user_field else False
    pass_set = bool(getattr(settings, pass_field, "").strip()) if pass_field else False

    current = f"current={spec.mode.value}"

    if spec.mode.value == "programmatic":
        could_be = "could_be=PROGRAMMATIC (already)"
        gap = "gap=none"
        if not user_set or (pass_field and not pass_set):
            gap = (
                f"gap=credentials_missing "
                f"({user_field}={'set' if user_set else 'empty'}, "
                f"{pass_field}={'set' if pass_set else 'empty'})"
            )
        return current, could_be, gap

    if spec.mode.value == "header_injection":
        mfa = _DEFERRED_MFA.get(vendor, "unknown")
        return (
            current,
            "could_be=PROGRAMMATIC",
            f"gap=no_loginflow_module (deferred — MFA risk: {mfa})",
        )

    # PROFILE_ONLY
    if user_set and pass_set:
        mfa = _DEFERRED_MFA.get(vendor)
        gap = (
            f"gap=no_loginflow_module (deferred — MFA risk: {mfa})"
            if mfa
            else "gap=no_loginflow_module"
        )
        return current, "could_be=PROGRAMMATIC", gap
    return current, "could_be=PROFILE_ONLY (no creds)", "gap=none"


async def _smoke_fetch_one(
    vendor: str,
    spec,
    profile_dir: Path,
) -> tuple[object, bytes, str]:
    """Run discover(limit=1) + fetch one PDF. Returns (ref, bytes, fetch_path).

    Branches based on ``spec.fetch_in_session``:

    * False (most vendors): generic ``ingest.fetch.fetch_pdf(url, profile_dir)``
    * True (barclays, socgen): call ``crawler_{vendor}.fetch_pdfs(...)``
      so PDF bytes are pulled inside the same Playwright session that
      discovery just established.

    Raises:
        RuntimeError: with the literal "no_refs_in_window" in the
            message when discover returns []. Caller string-matches on
            this to render the right BLOCKED reason.
    """
    # The playground crawlers are imported via the ``ingest.crawler_X``
    # path — same convention as ingest_today.py uses.
    project_root = Path(__file__).resolve().parents[4]
    play_root = str(project_root / "playground" / "research")
    if play_root not in sys.path:
        sys.path.insert(0, play_root)

    crawler_mod = importlib.import_module(f"ingest.crawler_{vendor}")
    discover_reports = crawler_mod.discover_reports

    today = date.today()
    refs = await discover_reports(
        profile_dir=profile_dir,
        since=today - timedelta(days=7),
        until=today,
    )
    if not refs:
        raise RuntimeError("no_refs_in_window (discover returned empty)")
    ref = refs[0]

    if spec.fetch_in_session:
        # In-session generator path (Barclays, SocGen).
        fetch_pdfs = getattr(crawler_mod, "fetch_pdfs", None)
        if fetch_pdfs is None:
            raise RuntimeError(
                f"crawler_{vendor} is marked fetch_in_session=True but "
                f"exposes no fetch_pdfs() generator"
            )
        data: bytes | None = None
        async for _ref, body in fetch_pdfs(profile_dir, [ref]):
            data = body
            break
        if data is None:
            raise RuntimeError("in_session_fetch returned None")
        return ref, data, "in_session"

    # Generic path.
    from ingest.fetch import fetch_pdf
    data = await fetch_pdf(ref.pdf_url, profile_dir)
    return ref, data, "generic"


def _validate_pdf_bytes(data: bytes, *, vendor: str) -> int:
    """Validate PDF magic + size + parse. Returns ``n_pages`` (``-1``
    when ``pypdf`` is unavailable, in which case only magic + size are
    enforced).

    Raises:
        PDFValidationError: with ``reason`` set to one of ``"empty"``,
            ``"bad_magic"``, ``"too_small"``, ``"pypdf_parse_failed"``,
            ``"zero_pages"``.
    """
    import io

    n_bytes = len(data) if data else 0
    if not data:
        raise PDFValidationError(
            "empty bytes", vendor=vendor, n_bytes=0, reason="empty",
        )
    if data[:4] != b"%PDF":
        raise PDFValidationError(
            f"bad magic ({data[:8]!r})",
            vendor=vendor, n_bytes=n_bytes, reason="bad_magic",
        )
    if n_bytes < 1024:
        raise PDFValidationError(
            f"too small ({n_bytes} bytes; probable error page)",
            vendor=vendor, n_bytes=n_bytes, reason="too_small",
        )
    try:
        from pypdf import PdfReader
    except ImportError:
        return -1
    try:
        reader = PdfReader(io.BytesIO(data))
        n_pages = len(reader.pages)
    except Exception as exc:
        raise PDFValidationError(
            f"pypdf parse failed: {type(exc).__name__}: {exc!s:.120}",
            vendor=vendor, n_bytes=n_bytes, reason="pypdf_parse_failed",
        ) from exc
    if n_pages < 1:
        raise PDFValidationError(
            "0 pages",
            vendor=vendor, n_bytes=n_bytes, reason="zero_pages",
        )
    return n_pages


async def _validate_one(vendor: str) -> _OutcomeRecord:
    """Run the 5-step validate flow for one vendor. Returns a structured
    outcome record so :func:`_cmd_validate` can assemble the summary
    email payload without re-parsing the BLOCKED reason string."""

    from ._paths import profile_dir
    from .context import get_authed_context

    spec = get_spec(vendor)
    started = time.perf_counter()

    print()
    print("=" * 72)
    print(f"  validate: {vendor}")
    print("=" * 72)

    # ----- Step 1: verify -----
    print("[1/5] current auth status")
    r1 = await verify(vendor)
    print(f"      mode={spec.mode.value}  verify -> {r1.status.value}")
    print(f"      url={spec.healthcheck_url}")
    if r1.detail:
        print(f"      detail: {r1.detail[:200]}")

    # ----- Step 2: credential gap -----
    current, could_be, gap = _step2_lines(vendor, spec)
    print("[2/5] credential availability (what it could be)")
    print(f"      {current}  {could_be}")
    print(f"      {gap}")

    def _record(rc: int, smoke: str, reason: str) -> _OutcomeRecord:
        return _OutcomeRecord(
            vendor=vendor,
            rc=rc,
            mode=spec.mode.value,
            status=r1.status.value,
            smoke=smoke,
            elapsed_s=time.perf_counter() - started,
            reason=reason,
        )

    # If session is not LIVE AND the vendor can't auto-recover, bail.
    if r1.status != SessionStatus.LIVE and spec.mode.value != "programmatic":
        print("[3/5] login + persist session")
        print(f"      SKIPPED — session is {r1.status.value} and not auto-recoverable")
        print("[4/5] download one PDF")
        print("      SKIPPED")
        print("[5/5] BLOCKED")
        record = _record(2, "BLOCKED", "needs_human")
        print(
            f"      vendor={vendor} mode={spec.mode.value} "
            f"current={r1.status.value} smoke=BLOCKED "
            f"reason=needs_human url={spec.healthcheck_url} "
            f"elapsed={record.elapsed_s:.1f}s"
        )
        return record

    # ----- Step 3: login + snapshot -----
    print("[3/5] login + persist session")
    step3_start = time.perf_counter()

    # Suppress double-emails: get_authed_context auto-emails on
    # CredentialMissing / LoginFailedError, but validate generates its
    # own summary email — silence that path here.
    prev_email_env = os.environ.get("IMDR_RESEARCH_AUTH_EMAIL_ON_AUTH_FAILURE")
    os.environ["IMDR_RESEARCH_AUTH_EMAIL_ON_AUTH_FAILURE"] = "false"
    try:
        try:
            async with get_authed_context(vendor) as _ctx:
                pass        # PROGRAMMATIC auto-login happens during __aenter__
        except AuthError as exc:
            print(f"      FAILED — {type(exc).__name__}: {exc!s:.200}")
            print("[4/5] download one PDF")
            print("      SKIPPED")
            print("[5/5] BLOCKED")
            reason = (
                "credentials_missing"
                if isinstance(exc, CredentialMissing)
                else "login_failed"
            )
            record = _record(2, "BLOCKED", reason)
            print(
                f"      vendor={vendor} mode={spec.mode.value} smoke=BLOCKED "
                f"reason={reason} elapsed={record.elapsed_s:.1f}s"
            )
            return record
        except Exception as exc:
            print(f"      FAILED — {type(exc).__name__}: {exc!s:.200}")
            print("[4/5] download one PDF")
            print("      SKIPPED")
            print("[5/5] BLOCKED")
            record = _record(2, "BLOCKED", f"login_failed:{type(exc).__name__}")
            print(
                f"      vendor={vendor} mode={spec.mode.value} smoke=BLOCKED "
                f"reason=login_failed elapsed={record.elapsed_s:.1f}s"
            )
            return record
    finally:
        if prev_email_env is None:
            os.environ.pop("IMDR_RESEARCH_AUTH_EMAIL_ON_AUTH_FAILURE", None)
        else:
            os.environ["IMDR_RESEARCH_AUTH_EMAIL_ON_AUTH_FAILURE"] = prev_email_env

    step3_elapsed = time.perf_counter() - step3_start
    snap = snapshot_path(vendor)
    print(f"      get_authed_context({vendor!r}) ok ({step3_elapsed:.1f}s)")
    if snap.exists():
        size_kb = snap.stat().st_size / 1024
        print(f"      storage_state snapshot -> {snap} ({size_kb:.1f} KB)")
    else:
        print("      [WARN] storage_state snapshot not written")

    # ----- Step 4: download + validate + delete one PDF -----
    print("[4/5] download one PDF")
    step4_start = time.perf_counter()
    try:
        ref, data, fetch_path = await _smoke_fetch_one(
            vendor, spec, profile_dir(vendor),
        )
    except Exception as exc:
        reason = (
            "no_refs_in_window"
            if "no_refs_in_window" in str(exc)
            else f"fetch_failed:{type(exc).__name__}"
        )
        print(f"      FAILED — {type(exc).__name__}: {exc!s:.200}")
        print("[5/5] BLOCKED")
        record = _record(2, "BLOCKED", reason)
        print(
            f"      vendor={vendor} mode={spec.mode.value} smoke=BLOCKED "
            f"reason={reason} elapsed={record.elapsed_s:.1f}s"
        )
        return record

    ref_uuid = (getattr(ref, "uuid", "") or "")[:10]
    ref_title = (getattr(ref, "title", "") or "")[:60]
    ref_url = (getattr(ref, "pdf_url", "") or "")[:80]
    print(f"      discover(limit=1) -> 1 ref  (fetch_path={fetch_path})")
    print(f"      ref.uuid={ref_uuid}  title={ref_title!r}")
    print(f"      pdf_url={ref_url}")

    # Write to temp; validate; always delete via os.unlink in the
    # outer finally. NamedTemporaryFile with delete=False is the
    # standard pattern when we want to control the unlink timing.
    tmp = tempfile.NamedTemporaryFile(  # noqa: SIM115 — manual unlink in finally
        suffix=".pdf", delete=False, prefix=f"validate_{vendor}_",
    )
    tmp_path = tmp.name
    try:
        try:
            tmp.write(data)
        finally:
            tmp.close()
        try:
            pages = _validate_pdf_bytes(data, vendor=vendor)
        except PDFValidationError as exc:
            print(
                f"      fetch_pdf -> {len(data):,} bytes  [INVALID: {exc}]  "
                f"({time.perf_counter() - step4_start:.1f}s)"
            )
            print("[5/5] BLOCKED")
            record = _record(2, "BLOCKED", f"bad_pdf:{exc.reason}")
            print(
                f"      vendor={vendor} mode={spec.mode.value} smoke=BLOCKED "
                f"reason=bad_pdf:{exc.reason} elapsed={record.elapsed_s:.1f}s"
            )
            return record
        page_str = "?" if pages == -1 else str(pages)
        print(
            f"      fetch_pdf -> {len(data):,} bytes  magic=%PDF  pages={page_str}  "
            f"({time.perf_counter() - step4_start:.1f}s)"
        )
    finally:
        try:
            os.unlink(tmp_path)
            print(f"      delete -> ok ({tmp_path})")
        except OSError as exc:
            print(f"      delete -> WARNING: {exc}")

    # ----- Step 5: SUCCESS -----
    print("[5/5] SUCCESS")
    record = _record(0, "PASS", "")
    print(
        f"      vendor={vendor} mode={spec.mode.value} "
        f"current={r1.status.value} {could_be} "
        f"smoke=PASS  elapsed={record.elapsed_s:.1f}s"
    )
    return record


async def _cmd_validate(args: argparse.Namespace) -> int:
    vendors = _resolve_vendors(args.vendor)
    no_email = bool(getattr(args, "no_email", False))
    dry_run_email = bool(getattr(args, "email_dry_run", False))

    if len(vendors) == 1:
        record = await _validate_one(vendors[0])
        return record.rc

    print(f"validate: {len(vendors)} vendor(s) sequentially")
    print(
        f"  expected runtime: ~{15 * len(vendors)}-{30 * len(vendors)}s "
        f"(real Playwright + HTTP per vendor)"
    )

    outcomes: list[_OutcomeRecord] = []
    for v in vendors:
        outcomes.append(await _validate_one(v))

    print()
    print("=" * 72)
    print(f"  summary: {len(vendors)} vendor(s)")
    print("=" * 72)
    n_pass = sum(1 for o in outcomes if o.smoke == "PASS")
    for o in outcomes:
        label = o.smoke if o.smoke == "PASS" else f"BLOCKED ({o.reason})"
        print(f"  {o.vendor:<10}  {label}")
    print(f"  {n_pass}/{len(vendors)} passed")

    # End-of-run summary email (silenced for single-vendor runs above).
    if not no_email or dry_run_email:
        try:
            from .notify import send_auth_email

            sent = send_auth_email(
                kind="validate_summary",
                dry_run=dry_run_email,
                n_pass=n_pass,
                n_total=len(outcomes),
                outcomes=[o.as_dict() for o in outcomes],
            )
            if sent and not dry_run_email:
                print("  [email] validate summary dispatched")
        except Exception as exc:
            print(f"  [email] dispatch raised (ignored): {type(exc).__name__}: {exc}")

    return 0 if n_pass == len(vendors) else 2


# ---------------------------------------------------------------------
# argparse wiring
# ---------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m imdr.research.auth",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_check = sub.add_parser("check", help="verify session liveness (read-only)")
    p_check.add_argument(
        "--vendor", default=None,
        help='vendor code, comma-list, or "all" (default: all)',
    )

    p_refresh = sub.add_parser("refresh", help="verify + auto-relog where possible")
    p_refresh.add_argument(
        "--vendor", default=None,
        help='vendor code, comma-list, or "all" (default: all)',
    )

    p_login = sub.add_parser("login", help="headed Chrome to seed/refresh SSO")
    p_login.add_argument(
        "--vendor", required=True, help="vendor code (one at a time)",
    )

    p_status = sub.add_parser(
        "status", help="last storage_state snapshot per vendor",
    )
    p_status.add_argument(
        "--vendor", default=None,
        help='vendor code, comma-list, or "all" (default: all)',
    )

    p_validate = sub.add_parser(
        "validate",
        help="full 5-step end-to-end smoke (login + snapshot + discover + 1 PDF + delete)",
    )
    p_validate.add_argument(
        "--vendor", default=None,
        help='vendor code, comma-list, or "all" (default: all)',
    )
    p_validate.add_argument(
        "--no-email", action="store_true",
        help="suppress the end-of-run summary email (only relevant for --vendor all)",
    )
    p_validate.add_argument(
        "--email-dry-run", action="store_true",
        help="render the summary email + print to stdout but do not dispatch",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.command == "check":
        return asyncio.run(_cmd_check(args))
    if args.command == "refresh":
        return asyncio.run(_cmd_refresh(args))
    if args.command == "login":
        return asyncio.run(_cmd_login(args))
    if args.command == "status":
        return _cmd_status(args)
    if args.command == "validate":
        return asyncio.run(_cmd_validate(args))
    raise SystemExit(f"unknown command {args.command!r}")


if __name__ == "__main__":
    sys.exit(main())
