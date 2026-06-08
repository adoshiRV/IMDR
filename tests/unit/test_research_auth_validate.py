"""Unit tests for the validate subcommand.

Mocks Playwright + crawler modules so the 5-step flow can be exercised
deterministically. The real validate command is operator-on-demand
(runs Playwright + HTTP per vendor); these tests cover the dispatch
logic, status-line formatting, and the temp-file deletion contract.
"""
from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager
from dataclasses import dataclass
from unittest.mock import patch

import pytest

from imdr.research.auth import cli as cli_mod
from imdr.research.auth.verify import SessionStatus, VerifyResult


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


@dataclass
class _FakeRef:
    uuid: str = "abc1234567"
    title: str = "Test report"
    pdf_url: str = "https://example.com/test.pdf"


def _minimal_pdf_bytes(n_pages: int = 1) -> bytes:
    """Synthesize a minimal valid PDF that pypdf can parse."""
    # Build a 1-page (or N-page) PDF by hand. Source:
    # the smallest valid PDF document.
    if n_pages < 1:
        n_pages = 1
    # Use a fixed minimal 1-page PDF and pad with junk to clear the
    # 1024-byte threshold. We don't need pypdf to count more than 1
    # page for the happy-path test.
    body = (
        b"%PDF-1.4\n"
        b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
        b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]>>endobj\n"
        b"xref\n0 4\n"
        b"0000000000 65535 f\n"
        b"0000000009 00000 n\n"
        b"0000000052 00000 n\n"
        b"0000000101 00000 n\n"
        b"trailer<</Size 4/Root 1 0 R>>\nstartxref\n160\n%%EOF\n"
    )
    if len(body) < 1024:
        # Pad to clear the 1024 threshold without breaking PDF parsing
        # (junk after %%EOF is tolerated by most parsers).
        body = body + b"\n%% padding " + b"x" * (1024 - len(body))
    return body


# ---------------------------------------------------------------------
# _validate_pdf_bytes — raises PDFValidationError with structured reason
# ---------------------------------------------------------------------

def test_validate_pdf_bytes_empty():
    from imdr.research.auth.errors import PDFValidationError

    with pytest.raises(PDFValidationError) as exc_info:
        cli_mod._validate_pdf_bytes(b"", vendor="x")
    assert exc_info.value.reason == "empty"
    assert exc_info.value.vendor == "x"
    assert exc_info.value.n_bytes == 0


def test_validate_pdf_bytes_bad_magic():
    from imdr.research.auth.errors import PDFValidationError

    with pytest.raises(PDFValidationError) as exc_info:
        cli_mod._validate_pdf_bytes(b"<html>not a pdf</html>" * 100, vendor="x")
    assert exc_info.value.reason == "bad_magic"


def test_validate_pdf_bytes_too_small():
    from imdr.research.auth.errors import PDFValidationError

    with pytest.raises(PDFValidationError) as exc_info:
        cli_mod._validate_pdf_bytes(b"%PDF-1.4\nsmall", vendor="x")
    assert exc_info.value.reason == "too_small"


def test_validate_pdf_bytes_valid_minimal():
    """Happy path — returns page count (>=1) or -1 when pypdf unavailable."""
    data = _minimal_pdf_bytes(1)
    pages = cli_mod._validate_pdf_bytes(data, vendor="x")
    # pypdf may or may not be installed; either way no exception.
    assert pages in (-1, 1)


# ---------------------------------------------------------------------
# _step2_lines — credential-gap analysis
# ---------------------------------------------------------------------

def _spec_with_mode(mode_value: str):
    """Pull a real spec and force its mode for predicate tests."""
    from imdr.research.auth.registry import VENDOR_AUTH_REGISTRY
    base = VENDOR_AUTH_REGISTRY["anz"]
    # Build a lightweight stand-in object with the minimum interface
    # _step2_lines uses (.mode.value).
    class _M:
        value = mode_value
    class _S:
        mode = _M()
        healthcheck_url = base.healthcheck_url
    return _S()


def test_step2_programmatic_with_creds():
    """Settings has creds + spec is PROGRAMMATIC → gap=none."""
    class _Settings:
        research_anz_username = "user@example.com"
        research_anz_password = "secret"
    with patch("imdr.config.settings.get_settings", return_value=_Settings()):
        current, could_be, gap = cli_mod._step2_lines(
            "anz", _spec_with_mode("programmatic"),
        )
    assert "programmatic" in current.lower()
    assert "already" in could_be.lower()
    assert "none" in gap.lower()


def test_step2_programmatic_missing_creds():
    """PROGRAMMATIC but Settings creds empty → gap reports it."""
    class _Settings:
        research_anz_username = ""
        research_anz_password = "secret"
    with patch("imdr.config.settings.get_settings", return_value=_Settings()):
        current, could_be, gap = cli_mod._step2_lines(
            "anz", _spec_with_mode("programmatic"),
        )
    assert "credentials_missing" in gap


def test_step2_profile_only_with_creds_flags_upgrade():
    """PROFILE_ONLY + creds available → could_be=PROGRAMMATIC."""
    class _Settings:
        research_anz_username = "user@example.com"
        research_anz_password = "secret"
    with patch("imdr.config.settings.get_settings", return_value=_Settings()):
        current, could_be, gap = cli_mod._step2_lines(
            "anz", _spec_with_mode("profile_only"),
        )
    assert "PROGRAMMATIC" in could_be
    assert "no_loginflow_module" in gap


def test_step2_header_injection_flags_mfa_risk():
    """JPM (header_injection) with deferred MFA → gap mentions MFA."""
    class _Settings:
        research_jpm_username = "user@example.com"
    with patch("imdr.config.settings.get_settings", return_value=_Settings()):
        _, could_be, gap = cli_mod._step2_lines(
            "jpm", _spec_with_mode("header_injection"),
        )
    assert "PROGRAMMATIC" in could_be
    assert "MFA" in gap


# ---------------------------------------------------------------------
# _smoke_fetch_one branching (in-session vs generic) — under mocks
# ---------------------------------------------------------------------

def _make_fake_crawler(refs, *, fetch_pdfs=None):
    """Build a fake crawler module that satisfies the validator's
    discover_reports + (optional) fetch_pdfs interface."""
    import types

    mod = types.ModuleType("ingest.crawler_fake")

    async def discover_reports(profile_dir, *, since=None, until=None, **_kw):
        return list(refs)

    mod.discover_reports = discover_reports
    if fetch_pdfs is not None:
        mod.fetch_pdfs = fetch_pdfs
    return mod


def test_smoke_fetch_one_generic_path(tmp_path):
    """Non-session-bound vendor → uses ingest.fetch.fetch_pdf."""
    from imdr.research.auth.registry import VENDOR_AUTH_REGISTRY

    spec = VENDOR_AUTH_REGISTRY["anz"]
    fake_ref = _FakeRef()

    pdf_bytes = _minimal_pdf_bytes()
    fake_crawler = _make_fake_crawler([fake_ref])

    # Build a fake ingest.fetch module exposing fetch_pdf.
    import types
    fake_fetch_mod = types.ModuleType("ingest.fetch")

    async def fake_fetch_pdf(url, profile_dir):
        return pdf_bytes

    fake_fetch_mod.fetch_pdf = fake_fetch_pdf

    import sys
    with patch.dict(
        sys.modules,
        {"ingest.crawler_anz": fake_crawler, "ingest.fetch": fake_fetch_mod},
    ):
        ref, data, path = _run(
            cli_mod._smoke_fetch_one("anz", spec, tmp_path),
        )
    assert ref is fake_ref
    assert data == pdf_bytes
    assert path == "generic"


def test_smoke_fetch_one_session_bound_path(tmp_path):
    """Session-bound vendor → uses crawler.fetch_pdfs() generator."""
    from imdr.research.auth.registry import VENDOR_AUTH_REGISTRY

    spec = VENDOR_AUTH_REGISTRY["barclays"]
    assert spec.fetch_in_session is True

    fake_ref = _FakeRef(uuid="bc987654", pdf_url="https://barcap.example/x.pdf")
    pdf_bytes = _minimal_pdf_bytes()

    async def fetch_pdfs(_profile_dir, refs):
        for r in refs:
            yield r, pdf_bytes

    fake_crawler = _make_fake_crawler([fake_ref], fetch_pdfs=fetch_pdfs)

    import sys
    with patch.dict(sys.modules, {"ingest.crawler_barclays": fake_crawler}):
        ref, data, path = _run(
            cli_mod._smoke_fetch_one("barclays", spec, tmp_path),
        )
    assert ref is fake_ref
    assert data == pdf_bytes
    assert path == "in_session"


def test_smoke_fetch_one_empty_discovery_raises(tmp_path):
    """discover() returning [] surfaces as a no_refs_in_window error."""
    from imdr.research.auth.registry import VENDOR_AUTH_REGISTRY

    spec = VENDOR_AUTH_REGISTRY["anz"]
    fake_crawler = _make_fake_crawler([])

    import sys
    with patch.dict(sys.modules, {"ingest.crawler_anz": fake_crawler}):
        with pytest.raises(RuntimeError, match="no_refs_in_window"):
            _run(cli_mod._smoke_fetch_one("anz", spec, tmp_path))


# ---------------------------------------------------------------------
# _validate_one — full 5-step orchestration under mocks
# ---------------------------------------------------------------------

def _stub_verify(status: SessionStatus, *, url: str = "", detail: str = ""):
    async def fake(_vendor):
        return VerifyResult(
            vendor="anz", status=status, url=url, detail=detail,
        )
    return patch("imdr.research.auth.cli.verify", side_effect=fake)


def _stub_authed_context_ok():
    @asynccontextmanager
    async def fake(_vendor, **_kw):
        yield object()
    # _validate_one does `from .context import get_authed_context` at
    # call time, so patch the source module.
    return patch("imdr.research.auth.context.get_authed_context", new=fake)


def _stub_authed_context_raises(exc):
    @asynccontextmanager
    async def fake(_vendor, **_kw):
        raise exc
        yield  # pragma: no cover
    return patch("imdr.research.auth.context.get_authed_context", new=fake)


def test_validate_one_happy_path(tmp_path, capsys):
    """LIVE + discover + fetch + valid PDF → exit code 0 (SUCCESS)."""
    pdf_bytes = _minimal_pdf_bytes()
    fake_ref = _FakeRef()

    async def fake_smoke(vendor, spec, profile_dir):
        return fake_ref, pdf_bytes, "generic"

    with _stub_verify(SessionStatus.LIVE, url="https://research.anz.com/all_research"), \
         _stub_authed_context_ok(), \
         patch("imdr.research.auth.cli._smoke_fetch_one", side_effect=fake_smoke), \
         patch("imdr.research.auth._paths.profile_dir", return_value=tmp_path), \
         patch("imdr.research.auth._paths.snapshot_path",
               return_value=tmp_path / "snap.json"):
        # Pre-create snapshot file so step 3 reports its size.
        (tmp_path / "snap.json").write_bytes(b"x" * 200)
        outcome = _run(cli_mod._validate_one("anz"))

    assert outcome.rc == 0
    assert outcome.smoke == "PASS"
    out = capsys.readouterr().out
    assert "[1/5]" in out
    assert "[5/5] SUCCESS" in out
    assert "smoke=PASS" in out


def test_validate_one_blocked_expired_profile_only(tmp_path, capsys):
    """PROFILE_ONLY + EXPIRED → BLOCKED with reason=needs_human."""
    with _stub_verify(SessionStatus.EXPIRED), \
         patch("imdr.research.auth._paths.profile_dir", return_value=tmp_path), \
         patch("imdr.research.auth._paths.snapshot_path",
               return_value=tmp_path / "snap.json"):
        outcome = _run(cli_mod._validate_one("bnp"))   # bnp is PROFILE_ONLY

    assert outcome.rc == 2
    assert outcome.smoke == "BLOCKED"
    assert outcome.reason == "needs_human"
    out = capsys.readouterr().out
    assert "smoke=BLOCKED" in out
    assert "needs_human" in out


def test_validate_one_blocked_login_fails(tmp_path, capsys):
    """PROGRAMMATIC + get_authed_context raises → BLOCKED reason=login_failed."""
    # AuthError forces the "credentials_missing|login_failed" branch; a
    # bare RuntimeError takes the generic catch-all. Use AuthError to
    # exercise the typed path the validate flow now expects.
    from imdr.research.auth.errors import LoginFailedError

    with _stub_verify(SessionStatus.EXPIRED), \
         _stub_authed_context_raises(LoginFailedError(
             vendor="barclays", title="Login", url="x")), \
         patch("imdr.research.auth._paths.profile_dir", return_value=tmp_path), \
         patch("imdr.research.auth._paths.snapshot_path",
               return_value=tmp_path / "snap.json"):
        outcome = _run(cli_mod._validate_one("barclays"))

    assert outcome.rc == 2
    assert outcome.smoke == "BLOCKED"
    assert outcome.reason == "login_failed"
    out = capsys.readouterr().out
    assert "login_failed" in out


def test_validate_one_blocked_no_refs(tmp_path, capsys):
    """discover returns [] → BLOCKED reason=no_refs_in_window."""
    async def fake_smoke(vendor, spec, profile_dir):
        raise RuntimeError("no_refs_in_window (discover returned empty)")

    with _stub_verify(SessionStatus.LIVE), \
         _stub_authed_context_ok(), \
         patch("imdr.research.auth.cli._smoke_fetch_one", side_effect=fake_smoke), \
         patch("imdr.research.auth._paths.profile_dir", return_value=tmp_path), \
         patch("imdr.research.auth._paths.snapshot_path",
               return_value=tmp_path / "snap.json"):
        (tmp_path / "snap.json").write_bytes(b"x")
        outcome = _run(cli_mod._validate_one("anz"))

    assert outcome.rc == 2
    assert outcome.reason == "no_refs_in_window"
    out = capsys.readouterr().out
    assert "no_refs_in_window" in out


def test_validate_one_blocked_bad_pdf(tmp_path, capsys):
    """Valid login + discover, but fetch returns garbage → BLOCKED."""
    fake_ref = _FakeRef()

    async def fake_smoke(vendor, spec, profile_dir):
        return fake_ref, b"<html>not a pdf</html>" * 100, "generic"

    with _stub_verify(SessionStatus.LIVE), \
         _stub_authed_context_ok(), \
         patch("imdr.research.auth.cli._smoke_fetch_one", side_effect=fake_smoke), \
         patch("imdr.research.auth._paths.profile_dir", return_value=tmp_path), \
         patch("imdr.research.auth._paths.snapshot_path",
               return_value=tmp_path / "snap.json"):
        (tmp_path / "snap.json").write_bytes(b"x")
        outcome = _run(cli_mod._validate_one("anz"))

    assert outcome.rc == 2
    assert outcome.reason.startswith("bad_pdf")
    out = capsys.readouterr().out
    assert "bad_pdf" in out


def test_validate_one_deletes_temp_file_on_success(tmp_path, capsys):
    """Confirm the temp PDF file is unlinked on the happy path."""
    pdf_bytes = _minimal_pdf_bytes()
    fake_ref = _FakeRef()
    seen_paths: list[str] = []

    real_unlink = os.unlink

    def tracking_unlink(p):
        seen_paths.append(p)
        return real_unlink(p)

    async def fake_smoke(vendor, spec, profile_dir):
        return fake_ref, pdf_bytes, "generic"

    with _stub_verify(SessionStatus.LIVE), \
         _stub_authed_context_ok(), \
         patch("imdr.research.auth.cli._smoke_fetch_one", side_effect=fake_smoke), \
         patch("imdr.research.auth._paths.profile_dir", return_value=tmp_path), \
         patch("imdr.research.auth._paths.snapshot_path",
               return_value=tmp_path / "snap.json"), \
         patch("os.unlink", side_effect=tracking_unlink):
        (tmp_path / "snap.json").write_bytes(b"x")
        outcome = _run(cli_mod._validate_one("anz"))

    assert outcome.rc == 0
    assert len(seen_paths) == 1, "exactly one temp file should be unlinked"
    assert not os.path.exists(seen_paths[0]), "temp file must be gone"
