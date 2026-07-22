"""Registry shape + predicate behaviour for imdr.research.auth."""
from __future__ import annotations

import pytest

from imdr.research.auth.registry import (
    VENDOR_AUTH_REGISTRY,
    AuthMode,
    all_vendors,
    get_spec,
)

# The 13 vendors currently wired into playground/research/ingest_today.py.
# UBS added 2026-06-08.
_EXPECTED_VENDORS = frozenset({
    "anz", "barclays", "bnp", "db", "goldman", "hsbc",
    "jpm", "ms", "nomura", "socgen", "stanc", "ubs", "westpac",
})


def test_all_expected_vendors_registered():
    assert set(VENDOR_AUTH_REGISTRY) == _EXPECTED_VENDORS


def test_all_vendors_returns_sorted():
    assert all_vendors() == tuple(sorted(_EXPECTED_VENDORS))


def test_get_spec_unknown_raises():
    """Raises UnknownVendor (which is also a KeyError subclass)."""
    from imdr.research.auth.errors import UnknownVendor

    with pytest.raises(UnknownVendor, match="unknown research vendor"):
        get_spec("bofa")  # BofA is PROD-HOLD, intentionally absent

    # KeyError backcompat — existing handlers keep working.
    with pytest.raises(KeyError):
        get_spec("bofa")


def test_barclays_is_programmatic_and_wipes_profile():
    spec = get_spec("barclays")
    assert spec.mode == AuthMode.PROGRAMMATIC
    assert spec.wipe_profile_per_run is True
    assert spec.login_module == "imdr.research.auth.loginflows.barclays"


def test_jpm_is_header_injection_with_factory():
    spec = get_spec("jpm")
    assert spec.mode == AuthMode.HEADER_INJECTION
    assert spec.extra_headers_factory is not None


def test_profile_only_vendors_have_no_login_module():
    for v in all_vendors():
        spec = get_spec(v)
        if spec.mode == AuthMode.PROFILE_ONLY:
            assert spec.login_module is None, (
                f"{v} is PROFILE_ONLY but has a login_module set"
            )


def test_ubs_spec_shape():
    spec = get_spec("ubs")
    assert spec.mode == AuthMode.PROGRAMMATIC
    assert spec.headless is False, "UBS rejects HeadlessChrome UA"
    assert spec.login_module == "imdr.research.auth.loginflows.ubs"
    assert spec.wipe_profile_per_run is False


@pytest.mark.parametrize("vendor,expected_module", [
    ("anz", "imdr.research.auth.loginflows.anz"),
    ("nomura", "imdr.research.auth.loginflows.nomura"),
    ("stanc", "imdr.research.auth.loginflows.stanc"),
    ("db", "imdr.research.auth.loginflows.db"),
])
def test_upgraded_vendors_are_programmatic(vendor, expected_module):
    spec = get_spec(vendor)
    assert spec.mode == AuthMode.PROGRAMMATIC, (
        f"{vendor} should be PROGRAMMATIC after the 2026-06-08 upgrade"
    )
    assert spec.login_module == expected_module


def test_fetch_in_session_only_for_session_bound_vendors():
    expected_in_session = {"barclays", "socgen"}
    for v in all_vendors():
        spec = get_spec(v)
        assert spec.fetch_in_session == (v in expected_in_session), (
            f"{v}.fetch_in_session={spec.fetch_in_session} "
            f"but expected {v in expected_in_session}"
        )


# Predicate behaviour — feed (title, url) pairs that mirror the
# real-world signals each vendor's is_authenticated check used.
@pytest.mark.parametrize("vendor,title,url,expected", [
    # Barclays: login page has "Login" in title and "ct_logon_basic"
    # in URL; authenticated home is /BU/.
    ("barclays", "Login - Barclays Live", "https://live.barcap.com/ct_logon_basic.do", False),
    ("barclays", "Home - Barclays Live", "https://live.barcap.com/BU/", True),
    ("barclays", "", "", False),  # blank → not live

    ("anz", "Login", "https://login.anz.com/sso", False),
    ("anz", "ANZ Research", "https://research.anz.com/all_research", True),

    ("bnp", "Sign in", "https://login.bnpparibas.com/", False),
    ("bnp", "Markets360", "https://markets360.bnpparibas.com/home", True),

    ("db", "Sign in", "https://login.db.com/", False),
    # Real logged-out landing: same host, path /research/Register, no
    # literal "login" — must be False (regression: 2026-07-22 it passed
    # as LIVE and the login poller exited before sign-in).
    ("db", "Register", "https://research.db.com/research/Register", False),
    ("db", "DB Research", "https://research.db.com/research/Research/Latest", True),

    ("goldman", "Sign in to Marquee", "https://login.marquee.gs.com/", False),
    ("goldman", "Marquee Research", "https://marquee.gs.com/s/", True),

    # HSBC: signed in → reach host; signed out → hsbcnet.com login.
    ("hsbc", "Sign On", "https://www.hsbcnet.com/gpib/login", False),
    ("hsbc", "HSBC Reach", "https://research.hsbc.com/ibcom/in/reach/servlet/Reach?productid=5", True),

    ("jpm", "Sign in", "https://login.jpmorgan.com/", False),
    ("jpm", "Research", "https://markets.jpmorgan.com/jpmm/research", True),

    ("ms", "Login", "https://login.ms.com/", False),
    ("ms", "Matrix", "https://ny.matrix.ms.com/eqr/research/portal/home/global", True),

    ("nomura", "Login", "https://login.nomuranow.com/", False),
    ("nomura", "Nomura Now", "https://www.nomuranow.com/portal/site/nnpub/research/", True),

    # SG: signed out flows through sgconnect.com.
    ("socgen", "SG Connect", "https://sso.sgconnect.com/sgconnect/auth", False),
    ("socgen", "Insight", "https://insight.sgmarkets.com/", True),

    ("stanc", "Sign in", "https://login.sc.com/", False),
    ("stanc", "Research", "https://research.sc.com/research/api/application/static/", True),

    ("westpac", "Sign in", "https://login.westpaciq.com.au/", False),
    ("westpac", "Westpac IQ", "https://www.westpaciq.com.au/economics", True),

    # UBS Neo: SSO bounces to /static/login.html when expired.
    ("ubs", "UBS Login", "https://neo.ubs.com/static/login.html", False),
    ("ubs", "UBS Neo", "https://neo.ubs.com/home", True),
])
def test_healthcheck_predicates(vendor: str, title: str, url: str, expected: bool):
    spec = get_spec(vendor)
    assert spec.healthcheck_predicate(title, url) is expected, (
        f"{vendor}.predicate({title!r}, {url!r}) expected {expected}"
    )


def test_every_vendor_has_healthcheck_url_and_predicate():
    for v in all_vendors():
        spec = get_spec(v)
        assert spec.healthcheck_url.startswith("http"), (
            f"{v} has no healthcheck_url"
        )
        assert callable(spec.healthcheck_predicate)
