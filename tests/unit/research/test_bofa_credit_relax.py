"""BofA Fold 2a pure-logic tests — credit-hub relaxation + login helpers.

Covers the logic that doesn't need live Outlook/BofA/DB:
  * `crawler_bofa._drop_reason` — single-name-corporate now KEPT in
    credit_* hubs, still DROPPED in non-credit hubs (scoped guard).
  * `filters/bofa.credit_hub_drop_reason` — keep-by-default for credit hubs.
  * `login_bofa._TOKEN_RE` — 8-digit token extraction (digits only).
  * `login_bofa._title_is_home` — positive home-title check.

Run:
    python -m pytest tests/unit/research/test_bofa_credit_relax.py -v
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_RESEARCH_ROOT = Path(__file__).resolve().parents[3] / "playground" / "research"
if str(_RESEARCH_ROOT) not in sys.path:
    sys.path.insert(0, str(_RESEARCH_ROOT))

from ingest.crawler_bofa import _drop_reason  # noqa: E402
from ingest.filters.bofa import credit_hub_drop_reason  # noqa: E402
from ingest.login_bofa import _TOKEN_RE, _title_is_home  # noqa: E402


# ---------------------------------------------------------------------------
# _drop_reason — single-name-corporate guard is credit-hub scoped
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("hub", [
    "credit_high_yield", "credit_em_corporate", "credit_high_grade",
    "credit_global", "credit_em_fi", "credit_securitized",
])
def test_single_name_kept_in_credit_hubs(hub: str) -> None:
    """Single-name issuer credit is KEPT in credit hubs (recall-first)."""
    assert _drop_reason(hub=hub, series="Kosmos Energy Ltd") is None


def test_single_name_still_dropped_in_non_credit_hub() -> None:
    """The guard is scoped: a single-name corporate in a NON-credit hub
    still drops (fx/rates/etc. behaviour unchanged)."""
    reason = _drop_reason(hub="fx_global", series="Kosmos Energy Ltd")
    assert reason is not None and reason.startswith("single-name-corporate")


def test_admin_series_still_dropped_in_credit_hub() -> None:
    """Recall-first doesn't disable the admin-series drop (stage 0)."""
    # 'reminder:' title prefix is an unconditional admin drop.
    assert _drop_reason(
        hub="credit_high_yield", series="Whatever",
        title="Reminder: conference call tomorrow",
    ) == "title-prefix:reminder"


# ---------------------------------------------------------------------------
# credit_hub_drop_reason — keep-by-default for credit hubs
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("series,title", [
    ("Kosmos Energy Ltd", "Kosmos Energy Ltd: 2026 outlook"),   # single-name
    ("Asia Gaming", "Genting complex credit update"),           # sector
    ("Some Series", "A non-macro credit note"),                 # generic
])
def test_credit_hub_keep_by_default(series: str, title: str) -> None:
    """Credit hubs no longer default-drop non-macro/non-strategy content."""
    assert credit_hub_drop_reason(
        hub="credit_em_corporate", series=series, title=title,
    ) is None


def test_credit_hub_reason_noop_for_non_credit_hub() -> None:
    assert credit_hub_drop_reason(
        hub="fx_global", series="x", title="y",
    ) is None


# ---------------------------------------------------------------------------
# _TOKEN_RE — 8-digit token, digits only
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("body,expected", [
    ("... Your token is: 28786410 IMPORTANT ...", "28786410"),
    ("Your token is:28437859\n", "28437859"),
    ("your TOKEN IS: 25962727", "25962727"),
])
def test_token_regex_extracts(body: str, expected: str) -> None:
    m = _TOKEN_RE.search(body)
    assert m is not None and m.group(1) == expected


def test_token_regex_ignores_alpha_noise() -> None:
    """Digits-only pattern must not latch onto a word after 'token is'."""
    assert _TOKEN_RE.search("Your token is available in the portal") is None


# ---------------------------------------------------------------------------
# _title_is_home — positive landing check
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("title,is_home", [
    ("Home - BofA Markets", True),
    ("Research - BofA Markets", True),
    ("Login - BofA Markets", False),
    ("", False),                       # blank/transitional title
    ("Additional Verification", False),
])
def test_title_is_home(title: str, is_home: bool) -> None:
    assert _title_is_home(title) is is_home
