"""Single source of truth for per-vendor research-portal auth config.

Each :class:`VendorAuthSpec` collapses what used to be open-coded into
each crawler's ``launch_persistent_context`` block + ``is_authenticated``
helper. The auth context manager in :mod:`.context` reads this registry
and acquires a :class:`BrowserContext` ready for the crawler to use.

Healthcheck predicate
---------------------
Each spec carries a ``healthcheck_url`` + ``healthcheck_predicate``.
The predicate receives ``(page_title, page_url)`` after we navigate
the healthcheck URL and returns True if the session is live. Predicates
are intentionally small — they mirror the body of each crawler's
existing ``is_authenticated`` helper (or the equivalent SSO-landing
test). When a vendor flips a login template, only the predicate needs
to change.

In scope
--------
The 12 vendors currently wired into ``playground/research/ingest_today.py``:
anz, barclays, bnp, db, goldman, hsbc, jpm, ms, nomura, socgen, stanc,
westpac. BofA is held out per the PROD-HOLD on
``docs/admin/research/scrapers/bofa.md``; UBS is not in the production
registry. Both can be added here later without changing the API.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum


class AuthMode(StrEnum):
    """How a vendor's session is established and recovered."""

    #: Persistent profile dir holds long-lived SSO cookies. Re-auth
    #: requires a human in headed Chrome — there is no programmatic
    #: form to fill.
    PROFILE_ONLY = "profile_only"

    #: A ``loginflows.{vendor}`` module owns a form-fill flow with
    #: credentials from :class:`Settings`. The auth context manager
    #: calls ``login()`` automatically when the session is stale.
    PROGRAMMATIC = "programmatic"

    #: Persistent SSO cookies PLUS a custom HTTP header injected on
    #: every request (e.g. JPM's ``janus_user``). The header is added
    #: via ``BrowserContext.set_extra_http_headers``.
    HEADER_INJECTION = "header_injection"


HealthcheckPredicate = Callable[[str, str], bool]


@dataclass(frozen=True, slots=True)
class VendorAuthSpec:
    """Per-vendor auth configuration."""

    code: str
    mode: AuthMode
    healthcheck_url: str
    healthcheck_predicate: HealthcheckPredicate
    headless: bool = True
    accept_downloads: bool = False
    wipe_profile_per_run: bool = False
    login_module: str | None = None      # dotted path under loginflows
    extra_headers_factory: Callable[[], dict[str, str]] | None = None
    #: True iff the vendor's PDF fetch must run in the same Playwright
    #: context as discover() — i.e. session-bound cookies that don't
    #: survive ``ctx.close()``. Only Barclays (PingFederate) and SocGen
    #: (doc-host OIDC) need this today; everyone else uses the generic
    #: ``ingest.fetch.fetch_pdf`` path. Read by the ``validate``
    #: subcommand to pick the right smoke-fetch branch.
    fetch_in_session: bool = False
    notes: str = ""


# ---------------------------------------------------------------------
# Healthcheck predicates
# ---------------------------------------------------------------------
# Each takes (title, url) and returns True iff the session is LIVE.
# When the page lands on a login screen, the predicate must return
# False. When the page errored / returned blank, the predicate must
# also return False (and let the caller treat it as EXPIRED).

def _live_barclays(title: str, url: str) -> bool:
    # Barclays Live: login page sets title containing "Login" and URL
    # contains "ct_logon_basic". Authenticated home is /BU/.
    return bool(title) and "Login" not in title and "ct_logon_basic" not in url


def _live_anz(title: str, url: str) -> bool:
    return "research.anz.com" in url and "login" not in url.lower()


def _live_bnp(title: str, url: str) -> bool:
    return "markets360.bnpparibas.com" in url and "login" not in url.lower()


def _live_db(title: str, url: str) -> bool:
    return "research.db.com" in url and "login" not in url.lower()


def _live_goldman(title: str, url: str) -> bool:
    return "marquee.gs.com" in url and "login" not in url.lower()


def _live_hsbc(title: str, url: str) -> bool:
    # Reach lives at /ibcom/in/reach/. Login redirects through
    # hsbcnet.com. Treat anything still on the Reach host as live.
    return "reach" in url.lower() and "hsbcnet.com" not in url.lower()


def _live_jpm(title: str, url: str) -> bool:
    return "markets.jpmorgan.com" in url and "login" not in url.lower()


def _live_ms(title: str, url: str) -> bool:
    return "ms.com" in url.lower() and "login" not in url.lower()


def _live_nomura(title: str, url: str) -> bool:
    return "nomuranow.com" in url and "login" not in url.lower()


def _live_socgen(title: str, url: str) -> bool:
    # SG: insight.sgmarkets.com is the authenticated landing; signin
    # flow redirects through sgconnect.com.
    return "insight.sgmarkets.com" in url and "sgconnect" not in url


def _live_stanc(title: str, url: str) -> bool:
    return "research.sc.com" in url and "login" not in url.lower()


def _live_westpac(title: str, url: str) -> bool:
    return "westpaciq.com.au" in url and "login" not in url.lower()


def _live_ubs(title: str, url: str) -> bool:
    # UBS Neo bounces unauthenticated traffic to /static/login.html;
    # the authenticated landing keeps the /home path.
    return "neo.ubs.com" in url and "/static/login.html" not in url


# ---------------------------------------------------------------------
# Header factories
# ---------------------------------------------------------------------

def _jpm_extra_headers() -> dict[str, str]:
    """``janus_user`` is the per-portal-user header JPM requires on
    every GraphQL POST. Read at registry-consume time so missing creds
    surface only when JPM is actually accessed.
    """
    from imdr.config.settings import get_settings

    user = (get_settings().research_jpm_username or "").strip()
    if not user:
        raise RuntimeError(
            "IMDR_RESEARCH_JPM_USERNAME is required for the JPM crawler "
            "(threaded into the `janus_user` GraphQL request header). "
            "Set it in .env or shell env."
        )
    return {"janus_user": user}


# ---------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------

VENDOR_AUTH_REGISTRY: dict[str, VendorAuthSpec] = {
    "anz": VendorAuthSpec(
        code="anz",
        mode=AuthMode.PROGRAMMATIC,
        healthcheck_url="https://research.anz.com/all_research",
        healthcheck_predicate=_live_anz,
        login_module="imdr.research.auth.loginflows.anz",
        notes="Programmatic form login (selectors best-guess, "
              "verify via `validate --vendor anz`). MFA fallback: "
              "revert to PROFILE_ONLY if validate reports MFA gate.",
    ),
    "barclays": VendorAuthSpec(
        code="barclays",
        mode=AuthMode.PROGRAMMATIC,
        healthcheck_url="https://live.barcap.com",
        healthcheck_predicate=_live_barclays,
        wipe_profile_per_run=True,
        login_module="imdr.research.auth.loginflows.barclays",
        fetch_in_session=True,
        notes="PingFederate poisons persistent state — profile is "
              "wiped before every launch; programmatic re-login in ~5s. "
              "PDF fetch is session-bound (cookies don't survive ctx close).",
    ),
    "bnp": VendorAuthSpec(
        code="bnp",
        mode=AuthMode.PROFILE_ONLY,
        healthcheck_url="https://markets360.bnpparibas.com/",
        healthcheck_predicate=_live_bnp,
    ),
    "db": VendorAuthSpec(
        code="db",
        mode=AuthMode.PROFILE_ONLY,
        healthcheck_url="https://research.db.com/research/Research/Latest",
        healthcheck_predicate=_live_db,
    ),
    "goldman": VendorAuthSpec(
        code="goldman",
        mode=AuthMode.PROFILE_ONLY,
        healthcheck_url="https://marquee.gs.com/s/",
        healthcheck_predicate=_live_goldman,
    ),
    "hsbc": VendorAuthSpec(
        code="hsbc",
        mode=AuthMode.PROFILE_ONLY,
        healthcheck_url=(
            "https://research.hsbc.com/ibcom/in/reach/servlet/Reach?productid=5"
        ),
        healthcheck_predicate=_live_hsbc,
        notes="HSBC Reach — productid scoping is the structured signal.",
    ),
    "jpm": VendorAuthSpec(
        code="jpm",
        mode=AuthMode.HEADER_INJECTION,
        healthcheck_url="https://markets.jpmorgan.com/jpmm/research",
        healthcheck_predicate=_live_jpm,
        extra_headers_factory=_jpm_extra_headers,
        notes="SSO cookies + janus_user header (IMDR_RESEARCH_JPM_USERNAME).",
    ),
    "ms": VendorAuthSpec(
        code="ms",
        mode=AuthMode.PROFILE_ONLY,
        healthcheck_url="https://ny.matrix.ms.com/eqr/research/portal/home/global",
        healthcheck_predicate=_live_ms,
        notes="Matrix portal — canonical post-SSO entry per "
              "playground/research/explore_ms.py. Earlier "
              "/eqr/library/landing/research-library was wrong "
              "(library page redirects to login even with valid cookies; "
              "fixed 2026-06-09).",
    ),
    "nomura": VendorAuthSpec(
        code="nomura",
        mode=AuthMode.PROGRAMMATIC,
        healthcheck_url="https://www.nomuranow.com/portal/site/nnpub/research/",
        healthcheck_predicate=_live_nomura,
        login_module="imdr.research.auth.loginflows.nomura",
        notes="Programmatic form login (selectors best-guess). MFA "
              "fallback: revert to PROFILE_ONLY if validate reports MFA.",
    ),
    "socgen": VendorAuthSpec(
        code="socgen",
        mode=AuthMode.PROFILE_ONLY,
        healthcheck_url="https://insight.sgmarkets.com/",
        healthcheck_predicate=_live_socgen,
        fetch_in_session=True,
        notes="OIDC bearer hydrates into localStorage after SPA load — "
              "storage_state snapshot captures it. PDF fetch is "
              "session-bound (doc.sgmarkets.com cookies don't survive "
              "ctx close).",
    ),
    "stanc": VendorAuthSpec(
        code="stanc",
        mode=AuthMode.PROGRAMMATIC,
        healthcheck_url="https://research.sc.com/research/api/application/static/",
        healthcheck_predicate=_live_stanc,
        login_module="imdr.research.auth.loginflows.stanc",
        notes="Programmatic form login (selectors best-guess). MFA "
              "fallback: revert to PROFILE_ONLY if validate reports MFA.",
    ),
    "ubs": VendorAuthSpec(
        code="ubs",
        mode=AuthMode.PROGRAMMATIC,
        healthcheck_url="https://neo.ubs.com/home",
        healthcheck_predicate=_live_ubs,
        headless=False,                  # UBS rejects HeadlessChrome UA
        wipe_profile_per_run=False,      # cookies persist days-to-weeks
        login_module="imdr.research.auth.loginflows.ubs",
        notes="UBS Neo two-step form (email then password). Headless "
              "MUST be False; UBS rejects HeadlessChrome UA. No MFA "
              "on current user/device as of 2026-06-05.",
    ),
    "westpac": VendorAuthSpec(
        code="westpac",
        mode=AuthMode.PROFILE_ONLY,
        healthcheck_url="https://www.westpaciq.com.au/economics",
        healthcheck_predicate=_live_westpac,
    ),
}


def get_spec(vendor: str) -> VendorAuthSpec:
    """Return the spec for ``vendor`` — raises :class:`UnknownVendor`."""
    from .errors import UnknownVendor

    try:
        return VENDOR_AUTH_REGISTRY[vendor]
    except KeyError as exc:
        known = ", ".join(sorted(VENDOR_AUTH_REGISTRY))
        raise UnknownVendor(
            f"unknown research vendor {vendor!r}; known: {known}",
            vendor=vendor,
        ) from exc


def all_vendors() -> tuple[str, ...]:
    """Sorted tuple of registered vendor codes."""
    return tuple(sorted(VENDOR_AUTH_REGISTRY))


__all__ = [
    "VENDOR_AUTH_REGISTRY",
    "AuthMode",
    "HealthcheckPredicate",
    "VendorAuthSpec",
    "all_vendors",
    "get_spec",
]
