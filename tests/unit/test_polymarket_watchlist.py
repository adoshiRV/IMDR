"""Unit tests for the polymarket watchlist YAML loader."""
from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
import yaml

from scripts.prediction.polymarket.watchlist import (
    WatchlistError,
    active_slugs,
    asset_tag_map,
    load_watchlist,
    mark_pruned,
    snapshot_entries,
)


def _write(tmp_path: Path, payload: dict) -> Path:
    p = tmp_path / "watchlist.yml"
    p.write_text(yaml.safe_dump(payload), encoding="utf-8")
    return p


def test_load_minimal_entry(tmp_path: Path) -> None:
    p = _write(tmp_path, {"events": [{"slug": "foo-bar", "asset_tag": "oil_mena"}]})
    entries = load_watchlist(p)
    assert len(entries) == 1
    e = entries[0]
    assert e.slug == "foo-bar"
    assert e.asset_tag == "oil_mena"
    assert e.section is None
    assert not e.has_snapshot_meta
    assert not e.is_wildcard


def test_load_full_entry(tmp_path: Path) -> None:
    p = _write(tmp_path, {"events": [{
        "slug": "ecb-decision-in-june",
        "asset_tag": "g10_cb",
        "section": "Europe / G10 CB",
        "label": "ECB June 2026 decision",
        "asset": "EUR",
        "market_read": "25bp cut fully priced",
        "event_date": "2026-06-04",
        "event_id": 287227,
    }]})
    e = load_watchlist(p)[0]
    assert e.event_date == date(2026, 6, 4)
    assert e.event_id == 287227
    assert e.has_snapshot_meta


def test_missing_path_returns_empty(tmp_path: Path) -> None:
    assert load_watchlist(tmp_path / "nonexistent.yml") == []


def test_missing_required_slug(tmp_path: Path) -> None:
    p = _write(tmp_path, {"events": [{"asset_tag": "oil_mena"}]})
    with pytest.raises(WatchlistError, match="missing required 'slug'"):
        load_watchlist(p)


def test_missing_required_asset_tag(tmp_path: Path) -> None:
    p = _write(tmp_path, {"events": [{"slug": "foo"}]})
    with pytest.raises(WatchlistError, match="missing required 'asset_tag'"):
        load_watchlist(p)


def test_invalid_slug(tmp_path: Path) -> None:
    p = _write(tmp_path, {"events": [{"slug": "Foo Bar!", "asset_tag": "oil_mena"}]})
    with pytest.raises(WatchlistError, match="invalid slug"):
        load_watchlist(p)


def test_invalid_asset_tag(tmp_path: Path) -> None:
    p = _write(tmp_path, {"events": [{"slug": "foo", "asset_tag": "BAD-TAG"}]})
    with pytest.raises(WatchlistError, match="invalid asset_tag"):
        load_watchlist(p)


def test_duplicate_slug(tmp_path: Path) -> None:
    p = _write(tmp_path, {"events": [
        {"slug": "foo", "asset_tag": "oil_mena"},
        {"slug": "foo", "asset_tag": "us_data"},
    ]})
    with pytest.raises(WatchlistError, match="duplicate slug"):
        load_watchlist(p)


def test_invalid_pruned_reason(tmp_path: Path) -> None:
    p = _write(tmp_path, {"events": [{
        "slug": "foo", "asset_tag": "oil_mena",
        "pruned": True, "pruned_reason": "WHATEVER",
    }]})
    with pytest.raises(WatchlistError, match="pruned_reason must be one of"):
        load_watchlist(p)


def test_event_id_must_be_int(tmp_path: Path) -> None:
    p = _write(tmp_path, {"events": [{
        "slug": "foo", "asset_tag": "oil_mena", "event_id": "not-an-int",
    }]})
    with pytest.raises(WatchlistError, match="event_id must be int"):
        load_watchlist(p)


def test_active_slugs_excludes_wildcard_and_pruned(tmp_path: Path) -> None:
    p = _write(tmp_path, {"events": [
        {"slug": "concrete", "asset_tag": "oil_mena"},
        {"slug": "wild-card-*", "asset_tag": "oil_mena"},
        {"slug": "pruned-one", "asset_tag": "oil_mena",
         "pruned": True, "pruned_reason": "MISSING"},
    ]})
    entries = load_watchlist(p)
    assert active_slugs(entries) == ["concrete"]


def test_asset_tag_map_excludes_pruned(tmp_path: Path) -> None:
    p = _write(tmp_path, {"events": [
        {"slug": "live", "asset_tag": "oil_mena"},
        {"slug": "dead", "asset_tag": "us_fed", "pruned": True, "pruned_reason": "DEAD"},
    ]})
    tags = asset_tag_map(load_watchlist(p))
    assert tags == {"live": "oil_mena"}


def test_snapshot_entries_requires_full_metadata(tmp_path: Path) -> None:
    p = _write(tmp_path, {"events": [
        {"slug": "polling-only", "asset_tag": "oil_mena"},
        {"slug": "snapshot-row", "asset_tag": "oil_mena",
         "section": "Geopolitics / Oil", "label": "Foo", "asset": "Oil"},
    ]})
    snap = snapshot_entries(load_watchlist(p))
    assert [e.slug for e in snap] == ["snapshot-row"]


def test_mark_pruned_round_trip(tmp_path: Path) -> None:
    p = _write(tmp_path, {"events": [
        {"slug": "alive", "asset_tag": "oil_mena"},
        {"slug": "to-prune-1", "asset_tag": "us_data"},
        {"slug": "to-prune-2", "asset_tag": "us_data"},
    ]})
    n = mark_pruned(p, {"to-prune-1": "DEAD", "to-prune-2": "MISSING"}, date(2026, 5, 4))
    assert n == 2

    bak = p.with_name(p.name + ".bak")
    assert bak.exists(), "mark_pruned must create .bak before writing"

    entries = load_watchlist(p)
    by_slug = {e.slug: e for e in entries}
    assert by_slug["alive"].pruned is False
    assert by_slug["to-prune-1"].pruned is True
    assert by_slug["to-prune-1"].pruned_reason == "DEAD"
    assert by_slug["to-prune-1"].pruned_at == date(2026, 5, 4)
    assert by_slug["to-prune-2"].pruned_reason == "MISSING"


def test_mark_pruned_idempotent_on_already_pruned(tmp_path: Path) -> None:
    p = _write(tmp_path, {"events": [
        {"slug": "old", "asset_tag": "oil_mena",
         "pruned": True, "pruned_at": "2026-05-01", "pruned_reason": "MISSING"},
    ]})
    n = mark_pruned(p, {"old": "DEAD"}, date(2026, 5, 4))
    assert n == 0
    e = load_watchlist(p)[0]
    assert e.pruned_at == date(2026, 5, 1), "previously-pruned entries are not overwritten"
    assert e.pruned_reason == "MISSING"


def test_mark_pruned_no_changes_does_not_write_bak(tmp_path: Path) -> None:
    p = _write(tmp_path, {"events": [{"slug": "alive", "asset_tag": "oil_mena"}]})
    n = mark_pruned(p, {"unrelated-slug": "DEAD"}, date(2026, 5, 4))
    assert n == 0
    assert not p.with_name(p.name + ".bak").exists()


# ---------------------------------------------------------------------------
# Sub-market question-date parser (macro_snapshot horizon disambiguation).
# ---------------------------------------------------------------------------

from scripts.prediction.polymarket.macro_snapshot import (  # noqa: E402
    _pick_modal,
    extract_question_date,
)


@pytest.mark.parametrize("question, default_year, expected", [
    # Explicit "by Month Day, Year"
    ("US x Iran permanent peace deal by June 30, 2026?", 2026, date(2026, 6, 30)),
    ("US x Iran permanent peace deal by December 31, 2026?", 2026, date(2026, 12, 31)),
    # "by Month Day" without year — falls back to default_year.
    ("Will Trump visit China by June 30?", 2026, date(2026, 6, 30)),
    ("Will Trump visit China by May 15?", 2026, date(2026, 5, 15)),
    # "by end of {month}"
    ("Strait of Hormuz traffic returns to normal by end of May?", 2026, date(2026, 5, 31)),
    ("Strait of Hormuz traffic returns to normal by end of June?", 2026, date(2026, 6, 30)),
    # "before YYYY" → preceding year-end.
    ("Will the U.S. invade Iran before 2027?", 2026, date(2026, 12, 31)),
    # "in YYYY"
    ("Will Israel strike 3 countries in 2026?", 2026, date(2026, 12, 31)),
    # Quarter
    ("Will US GDP growth in Q2 2026 be greater than 3.5%?", 2026, date(2026, 6, 30)),
    # CB meeting reference — anchored to mid-month.
    ("Bank of Japan increases interest rates by 25 bps after the June 2026 meeting?", 2026, date(2026, 6, 15)),
    # No date phrase → None.
    ("Will Benjamin Netanyahu be the next Prime Minister of Israel?", 2026, None),
    ("2026 Balance of Power: R Senate, D House", 2026, None),
])
def test_extract_question_date(question: str, default_year: int, expected: date | None) -> None:
    assert extract_question_date(question, default_year) == expected


class _Row(dict):
    """Tiny stand-in for sqlite3.Row supporting ['key'] access."""


def _row(question: str, yes: float) -> _Row:
    return _Row(question=question, yes_price=yes)


def test_pick_modal_prefers_horizon_match_over_highest_yes() -> None:
    # Iran peace ladder — Dec 31 is highest-yes but Jun 30 is the target.
    rows = [
        _row("US x Iran permanent peace deal by December 31, 2026?", 0.640),
        _row("US x Iran permanent peace deal by June 30, 2026?",     0.345),
        _row("US x Iran permanent peace deal by May 31, 2026?",      0.135),
    ]
    idx, qdate = _pick_modal(rows, target_date=date(2026, 6, 30))
    assert idx == 1
    assert qdate == date(2026, 6, 30)


def test_pick_modal_falls_back_to_highest_yes_when_no_dates_parse() -> None:
    # Bucket-style event where no question carries a date.
    rows = [
        _row("Will Person A be the next PM?", 0.42),
        _row("Will Person B be the next PM?", 0.31),
    ]
    idx, qdate = _pick_modal(rows, target_date=date(2026, 6, 30))
    assert idx == 0
    assert qdate is None


def test_pick_modal_legacy_when_target_date_is_none() -> None:
    rows = [
        _row("Will the US add between 50k and 100k jobs in April?", 0.27),
        _row("Will the US add between 0 and 50k jobs in April?", 0.255),
    ]
    idx, _ = _pick_modal(rows, target_date=None)
    assert idx == 0


def test_pick_modal_breaks_ties_by_yes_price() -> None:
    # NFP-style: every sub-question parses to "April" → 2026-04-30. All tied
    # at 30 days from event_date 2026-05-08. Tie breaks to highest yes.
    rows = [
        _row("Will the US add between 50k and 100k jobs in April?", 0.27),
        _row("Will the US add between 0 and 50k jobs in April?", 0.255),
        _row("Will the US add between 100k and 150k jobs in April?", 0.245),
    ]
    idx, _ = _pick_modal(rows, target_date=date(2026, 5, 8))
    assert idx == 0
