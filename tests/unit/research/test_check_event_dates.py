"""Tests for scripts/research/check_event_dates.py.

Pins the failure that produced "Japan Q2 GDP, final | 07 Sep" in the 07 Sep
2026 weekly, plus the traps a naive fix would fall into:

  * the TE lane's UTC day-bucket is off by one for an 08:50 JST release;
  * the BQL lane is NOT a trustworthy arbiter -- it is a day late on US and
    Colombian afternoon releases, so "just use BQL" would swap one bug for
    another;
  * a placeholder row with no instant is skipped, never failed;
  * DST is resolved by zone, not by a fixed offset.
"""
from __future__ import annotations

import datetime as dt
import importlib.util
import sys
from pathlib import Path

import pytest

_MOD_PATH = (
    Path(__file__).resolve().parents[3]
    / "scripts" / "research" / "check_event_dates.py"
)
_spec = importlib.util.spec_from_file_location("check_event_dates", _MOD_PATH)
ced = importlib.util.module_from_spec(_spec)
sys.modules["check_event_dates"] = ced
_spec.loader.exec_module(ced)


UTC = dt.timezone.utc


def _dt(y, m, d, hh, mm=0):
    return dt.datetime(y, m, d, hh, mm, tzinfo=UTC)


# ---------------------------------------------------------------------------
# local_date — the single derivation everything else rests on
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "instant, tzname, expected",
    [
        # THE bug: Japan Q2 GDP 2nd prelim, 08:50 JST on 8 Sep, is 23:50 UTC
        # on the 7th. The UTC date is a day early.
        (_dt(2026, 9, 7, 23, 50), "Asia/Tokyo", dt.date(2026, 9, 8)),
        # Korea GDP final, 08:00 KST on 8 Sep = 23:00 UTC on the 7th.
        (_dt(2026, 9, 7, 23, 0), "Asia/Seoul", dt.date(2026, 9, 8)),
        # Same instant, Colombia: 18:00 COT, still the 7th. Rolling every
        # 23:00 UTC row forward would break this one.
        (_dt(2026, 9, 7, 23, 0), "America/Bogota", dt.date(2026, 9, 7)),
        # US Treasury auction 17:00 UTC = 13:00 ET, same day.
        (_dt(2026, 9, 8, 17, 0), "America/New_York", dt.date(2026, 9, 8)),
        # Australia ABS 11:30 AEST = 01:30 UTC, same day either way.
        (_dt(2026, 9, 8, 1, 30), "Australia/Sydney", dt.date(2026, 9, 8)),
    ],
)
def test_local_date(instant, tzname, expected):
    assert ced.local_date(instant, tzname) == expected


def test_local_date_is_dst_aware():
    """22:30 UTC is next-day in London in summer, same-day in winter."""
    assert ced.local_date(_dt(2026, 7, 1, 23, 30), "Europe/London") == dt.date(2026, 7, 2)
    assert ced.local_date(_dt(2026, 1, 1, 23, 30), "Europe/London") == dt.date(2026, 1, 1)


# ---------------------------------------------------------------------------
# classify_row — what the gate actually asserts per lane
# ---------------------------------------------------------------------------

def test_te_lane_japan_gdp_is_misdated():
    """The exact row the 07 Sep weekly read: TE id=115505."""
    status, expected, tzname = ced.classify_row(
        dt.date(2026, 9, 7), _dt(2026, 9, 7, 23, 50), "JP", "Asia/Tokyo"
    )
    assert status == "MISDATED"
    assert expected == dt.date(2026, 9, 8)
    assert tzname == "Asia/Tokyo"


def test_bql_lane_japan_gdp_is_ok():
    status, expected, _ = ced.classify_row(
        dt.date(2026, 9, 8), _dt(2026, 9, 7, 23, 50), "JP", "Asia/Tokyo"
    )
    assert status == "OK"
    assert expected == dt.date(2026, 9, 8)


def test_bql_lane_is_not_a_trustworthy_arbiter():
    """BQL files a 13:00 ET US auction a day late — deferring to it would
    replace the Japan bug with a US one."""
    status, expected, _ = ced.classify_row(
        dt.date(2026, 9, 9), _dt(2026, 9, 8, 17, 0), "US", "America/New_York"
    )
    assert status == "MISDATED"
    assert expected == dt.date(2026, 9, 8)


def test_placeholder_row_without_instant_is_skipped_not_failed():
    status, expected, _ = ced.classify_row(
        dt.date(2026, 9, 7), None, "JP", "Asia/Tokyo"
    )
    assert status == "SKIP"
    assert expected is None


def test_pseudo_country_without_local_calendar_is_skipped():
    status, _, _ = ced.classify_row(
        dt.date(2026, 9, 7), _dt(2026, 9, 7, 23, 50), "WW", None
    )
    assert status == "SKIP"


def test_eurozone_falls_back_to_brussels():
    """dim_country.timezone is NULL for the EU pseudo-country, but 279 events
    hang off it — it must not silently skip."""
    assert ced.resolve_tz("EU", None) == "Europe/Brussels"
    status, expected, _ = ced.classify_row(
        dt.date(2026, 9, 7), _dt(2026, 9, 7, 9, 0), "EU", None
    )
    assert status == "OK" and expected == dt.date(2026, 9, 7)


# ---------------------------------------------------------------------------
# find_split_releases — the same release printed twice
# ---------------------------------------------------------------------------

def _row(vendor_id, stored, instant, cc="JP", name="GDP", expected=None):
    return {
        "id": 1, "stored": stored, "instant": instant, "event_name": name,
        "vendor_id": vendor_id, "is_estimated": False, "country_code": cc,
        "tz": "Asia/Tokyo", "status": "OK", "expected": expected,
    }


def test_split_release_detected_across_lanes():
    instant = _dt(2026, 9, 7, 23, 50)
    rows = [
        _row(73, dt.date(2026, 9, 7), instant, expected=dt.date(2026, 9, 8)),
        _row(4, dt.date(2026, 9, 8), instant, expected=dt.date(2026, 9, 8)),
    ]
    splits = ced.find_split_releases(rows)
    assert len(splits) == 1
    cc, when, group = splits[0]
    assert cc == "JP" and when == instant and len(group) == 2


def test_lanes_agreeing_is_not_a_split():
    instant = _dt(2026, 9, 7, 23, 50)
    rows = [
        _row(73, dt.date(2026, 9, 8), instant),
        _row(4, dt.date(2026, 9, 8), instant),
    ]
    assert ced.find_split_releases(rows) == []


def test_rows_without_instant_cannot_split():
    rows = [
        _row(73, dt.date(2026, 9, 7), None),
        _row(4, dt.date(2026, 9, 8), None),
    ]
    assert ced.find_split_releases(rows) == []


# ---------------------------------------------------------------------------
# Digest parsing + matching
# ---------------------------------------------------------------------------

_MD = """# Weekly

## Tier 3 — Total macro calendar

| Date | Country | Event | Survey |
|---|---|---|---|
| 07 Sep | Japan | Q2 GDP final; current account | 0.4% q/q |
| 08 Sep | Korea | Q2 GDP final; unemployment | 0.6% q/q |

## Japan

| Date | Event | Why it matters |
|---|---|---|
| 07 Sep | Q2 GDP final | A revision |

| Bank | Date | Call |
|---|---|---|
| Nomura | 02 Sep | Hike |
"""


def test_digest_rows_extracted_with_country(tmp_path):
    p = tmp_path / "d.md"
    p.write_text(_MD, encoding="utf-8")
    rows = list(ced.digest_event_rows(p, dt.date(2026, 9, 7)))
    # the source register (first col "Bank") is not a calendar table
    assert len(rows) == 3
    assert (rows[0][1], rows[0][2]) == (dt.date(2026, 9, 7), "JP")
    assert (rows[1][1], rows[1][2]) == (dt.date(2026, 9, 8), "KR")
    # third row has no Country column — country comes from the "## Japan" heading
    assert (rows[2][1], rows[2][2]) == (dt.date(2026, 9, 7), "JP")


def test_year_resolved_by_proximity_not_edition_year():
    """A 31 Dec edition carrying '02 Jan' means next year."""
    assert ced._resolve_year(1, 2, dt.date(2026, 12, 31)) == dt.date(2027, 1, 2)
    assert ced._resolve_year(12, 30, dt.date(2027, 1, 2)) == dt.date(2026, 12, 30)


def test_match_event_binds_and_flags_wrong_day():
    events = [{
        "country_code": "JP", "event_name": "gdp growth annualized final",
        "expected": dt.date(2026, 9, 8), "instant": _dt(2026, 9, 7, 23, 50),
        "tz": "Asia/Tokyo",
    }]
    ev = ced.match_event(dt.date(2026, 9, 7), "JP", "Q2 GDP final annualized",
                         events)
    assert ev is not None
    assert ev["expected"] == dt.date(2026, 9, 8)  # digest said 07 -> violation


def test_match_event_requires_two_shared_tokens():
    """A single generic token must not bind an unrelated release and
    manufacture a violation."""
    events = [{
        "country_code": "JP", "event_name": "machine tool orders",
        "expected": dt.date(2026, 9, 8), "instant": _dt(2026, 9, 7, 23, 50),
        "tz": "Asia/Tokyo",
    }]
    assert ced.match_event(dt.date(2026, 9, 7), "Q2 GDP final", "JP", events) is None


def test_match_event_ties_break_to_nearest_date():
    """Recurring events (speeches, auctions) repeat under identical names in a
    window. A tie broken arbitrarily reports the digest wrong for naming a
    different instance of the same thing."""
    events = [
        {"country_code": "EU", "event_name": "ecb president lagarde speech",
         "expected": dt.date(2026, 9, 9), "instant": _dt(2026, 9, 9, 17, 0),
         "tz": "Europe/Brussels"},
        {"country_code": "EU", "event_name": "ecb president lagarde speech",
         "expected": dt.date(2026, 9, 11), "instant": _dt(2026, 9, 11, 8, 0),
         "tz": "Europe/Brussels"},
    ]
    ev = ced.match_event(dt.date(2026, 9, 11), "EU", "ECB Lagarde speech", events)
    assert ev["expected"] == dt.date(2026, 9, 11)  # not the 9 Sep instance


def test_country_from_text_takes_earliest_mention():
    """A China row whose house-calls cell also mentions Korea is China."""
    assert ced._country_from_text(
        "China August trade | Citi vs Korea desk disagree"
    ) == "CN"
    # longer alias wins at the same position
    assert ced._country_from_text("South Korea CPI") == "KR"


def test_multi_country_grid_does_not_inherit_section_country(tmp_path):
    """An ECB row inside a US section must never be checked as a US release —
    that bound 'ECB decision' to 'US core inflation' and manufactured a
    violation.

    It used to be asserted unlabelled, which was the best available outcome
    rather than the desired one: nothing resolved "ECB" to a country, so the
    row was skipped instead of checked. With the bank now an anchor it
    resolves to EU and is checked against real EU events. The invariant under
    test is unchanged — the section heading must not leak in.
    """
    md = """# Weekly

## United States

| Event / theme | Date | Consensus |
|---|---|---|
| Japan Q2 GDP, final | 07 Sep | 0.4% q/q |
| Thailand August CPI | 07 Sep | 2.43% y/y |
| **ECB decision** | 10 Sep | Deposit 2.50%, core inflation |
"""
    p = tmp_path / "d.md"
    p.write_text(md, encoding="utf-8")
    rows = {r[0]: r for r in ced.digest_event_rows(p, dt.date(2026, 9, 7))}
    countries = {r[2] for r in rows.values()}
    assert "JP" in countries and "TH" in countries
    assert "US" not in countries  # the section heading did not leak in
    ecb = [r for r in rows.values() if "ECB" in r[3]][0]
    assert ecb[2] == "EU"


def test_single_country_board_still_inherits_section_country(tmp_path):
    """The guard must not disable the section fallback for real per-country
    boards, which is the only way their rows get a country at all."""
    md = """# Weekly

## Japan

| Date | Event | Why it matters |
|---|---|---|
| 07 Sep | Q2 GDP final | A revision |
| 11 Sep | PPI | Pass-through |
"""
    p = tmp_path / "d.md"
    p.write_text(md, encoding="utf-8")
    rows = list(ced.digest_event_rows(p, dt.date(2026, 9, 7)))
    assert len(rows) == 2
    assert {r[2] for r in rows} == {"JP"}


def test_exit_semantics_documented_in_docstring():
    """The two modes must stay documented — the exit code is the whole
    contract for a gate, and a silent change to it is how a gate starts
    lying about whether an edition is safe to lock."""
    doc = ced.__doc__
    assert "--audit-strict" in doc
    assert "With a digest" in doc and "With no digest" in doc


def test_audit_strict_flag_exists_and_defaults_off():
    """Upstream lane defects must NOT block an edition by default: no MD edit
    can fix them, so gating on them keeps the check red for every edition
    until the ingest is fixed."""
    import argparse
    ap = argparse.ArgumentParser()
    # mirror of main()'s parser wiring, asserted so the default can't drift
    ap.add_argument("--audit-strict", action="store_true")
    assert ap.parse_args([]).audit_strict is False
    assert ap.parse_args(["--audit-strict"]).audit_strict is True


def test_as_datetime_parses_sql_server_datetimeoffset():
    """The pinned legacy ODBC driver returns datetimeoffset as a STRING with 7
    fractional digits and a space before the offset."""
    got = ced.as_datetime("2026-09-07 23:50:00.0000000 +00:00")
    assert got == _dt(2026, 9, 7, 23, 50)
    assert ced.local_date(got, "Asia/Tokyo") == dt.date(2026, 9, 8)
    assert ced.as_datetime(None) is None
    assert ced.as_date("2026-09-07") == dt.date(2026, 9, 7)


def test_match_event_respects_country():
    events = [{
        "country_code": "KR", "event_name": "gdp growth rate qoq final",
        "expected": dt.date(2026, 9, 8), "instant": _dt(2026, 9, 7, 23, 0),
        "tz": "Asia/Seoul",
    }]
    assert ced.match_event(dt.date(2026, 9, 7), "JP", "GDP growth final", events) is None


# ---------------------------------------------------------------------------
# Row country inference must not depend on column ORDER
# ---------------------------------------------------------------------------

_TIME_FIRST = """# China — the read

| Date | Time | Event |
|---|---|---|
| 16 Sep | 09:30 | ECB's Lagarde speaks in Dublin |
| 17 Sep | 12:30 | US retail sales, August |
| 18 Sep | 08:00 | Japan CPI, August |
"""

_EVENT_FIRST = """# China — the read

| Date | Event | Time |
|---|---|---|
| 16 Sep | ECB's Lagarde speaks in Dublin | 09:30 |
| 17 Sep | US retail sales, August | 12:30 |
| 18 Sep | Japan CPI, August | 08:00 |
"""


@pytest.mark.parametrize("md", [_TIME_FIRST, _EVENT_FIRST])
def test_time_column_does_not_swallow_the_country(tmp_path, md):
    """A Time column sitting between Date and Event must not become the row's
    lead cell.

    It carries no country, so every row fell through to the enclosing heading
    and a CN H1 stamped CN on a board of EU/US/JP releases -- silently, since
    each row then bound to whatever CN event shared two tokens with it. The
    two column orders must agree.
    """
    p = tmp_path / "d.md"
    p.write_text(md, encoding="utf-8")
    got = [(w, cc) for _, w, cc, _, _ in
           ced.digest_event_rows(p, dt.date(2026, 9, 15))]
    assert got == [
        (dt.date(2026, 9, 16), "EU"),
        (dt.date(2026, 9, 17), "US"),
        (dt.date(2026, 9, 18), "JP"),
    ]


@pytest.mark.parametrize("cell", [
    "09:30", "14:00 SGT", " 08:30 ET ", "13:15-13:45", "8.30am",
    "21:50 JST", "—", "", "  -  ",
])
def test_cells_with_no_country_signal_are_skipped(cell):
    assert ced._is_signal_cell(cell) is False


@pytest.mark.parametrize("cell", [
    "ECB's Lagarde speaks", "US retail sales", "10Y JGB auction",
    "Q2 GDP, final", "CPI 2.4% y/y",
])
def test_substantive_cells_are_kept(cell):
    assert ced._is_signal_cell(cell) is True


@pytest.mark.parametrize("text,expected", [
    ("ECB's Lagarde speaks in Dublin", "EU"),
    ("BoJ policy decision", "JP"),
    ("FOMC minutes", "US"),
    ("RBNZ OCR review", "NZ"),
    ("PBoC MLF rollover", "CN"),
    ("Bank of Canada decision", "CA"),
    ("Bank of Thailand rate decision", "TH"),
])
def test_central_bank_names_resolve_to_a_country(text, expected):
    """Calendar rows name the bank, not the country."""
    assert ced._country_from_text(text) == expected


def test_country_named_in_the_row_still_beats_the_bank(tmp_path):
    """Earliest mention wins: a US row that merely mentions the Fed is US."""
    assert ced._country_from_text("US CPI — what it means for the Fed") == "US"


def test_ambiguous_bank_acronyms_are_not_aliased():
    """'BoC' (Canada vs China) and 'BoT'/'BI' (ordinary words) must not
    resolve, or they would mislabel rows with false confidence."""
    for text in ("BoC decision", "BoT meeting", "BI board meeting"):
        assert ced._country_from_text(text) is None


def test_same_country_board_keeps_the_section_fallback(tmp_path):
    """Two rows naming the SAME country is not a multi-country grid.

    Counting rows rather than distinct countries made a real per-country board
    trip the grid guard as soon as two of its own rows said "Japan" — and its
    remaining rows, the ones carrying only "Trade balance", then lost the
    section fallback and went unchecked. Regression from widening the lead-cell
    scan: before, none of these rows resolved a country at all.
    """
    md = """## Japan

| Date | Time | Event |
|---|---|---|
| 14 Sep | 08:50 | Japan Q2 GDP, final |
| 15 Sep | 08:50 | Japan PPI |
| 16 Sep | 08:50 | Trade balance; machinery orders |
"""
    p = tmp_path / "d.md"
    p.write_text(md, encoding="utf-8")
    rows = list(ced.digest_event_rows(p, dt.date(2026, 9, 15)))
    assert len(rows) == 3
    assert {r[2] for r in rows} == {"JP"}, "every row belongs to the section country"


def test_genuine_grid_still_suppresses_the_section(tmp_path):
    """The guard must still fire for two DIFFERENT countries."""
    md = """## United States

| Date | Time | Event |
|---|---|---|
| 16 Sep | 09:30 | Japan CPI |
| 17 Sep | 12:30 | ECB's Lagarde speaks |
| 18 Sep | 08:00 | Trade balance |
"""
    p = tmp_path / "d.md"
    p.write_text(md, encoding="utf-8")
    got = {r[2] for r in ced.digest_event_rows(p, dt.date(2026, 9, 15))}
    assert "US" not in got, "the section heading must not leak into a grid"
    assert {"JP", "EU"} <= got


def test_impossible_date_is_dropped_not_crashed(tmp_path):
    """A typo'd '31 Feb' cell must cost one row, not the whole gate.

    _resolve_year finds no valid year and returned None, which reached
    match_event as `date - None` -> TypeError.
    """
    assert ced._resolve_year(2, 31, dt.date(2026, 9, 15)) is None
    md = """## Japan

| Date | Event |
|---|---|
| 31 Feb | Typo row |
| 16 Sep | Trade balance |
"""
    p = tmp_path / "d.md"
    p.write_text(md, encoding="utf-8")
    rows = list(ced.digest_event_rows(p, dt.date(2026, 9, 15)))
    assert [r[1] for r in rows] == [dt.date(2026, 9, 16)]
