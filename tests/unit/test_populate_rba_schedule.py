"""Unit tests for the RBA meeting-schedule seed data.

Validates the static RBA_MEETINGS table without touching the database.
"""

from __future__ import annotations

from datetime import date, datetime

import pytest
from scripts.calendar.populate_rba_schedule import RBA_MEETINGS


def test_dates_are_unique_and_sorted():
    dates = [d for d, _dt, _est in RBA_MEETINGS]
    assert len(dates) == len(set(dates)), "duplicate meeting dates"
    assert dates == sorted(dates), "meeting dates must be chronological"


def test_expected_counts_per_year():
    by_year: dict[int, int] = {}
    for d, _dt, _est in RBA_MEETINGS:
        by_year[int(d[:4])] = by_year.get(int(d[:4]), 0) + 1
    assert by_year == {2027: 8, 2028: 5}


def test_2027_known_2028_projected():
    for d, event_dt, is_estimated in RBA_MEETINGS:
        year = int(d[:4])
        if year == 2027:
            assert is_estimated is False, f"{d} 2027 should be known/hard"
            assert event_dt is not None, f"{d} known meeting must carry a datetime"
        elif year == 2028:
            assert is_estimated is True, f"{d} 2028 should be projected/soft"
            assert event_dt is None, f"{d} projected meeting must have no datetime"


@pytest.mark.parametrize("d, event_dt, _est", RBA_MEETINGS)
def test_dates_parse_and_datetime_is_1430_sydney(d, event_dt, _est):
    # event_date parses
    date.fromisoformat(d)
    if event_dt is None:
        return
    # event_datetime is a valid UTC timestamp at 03:30Z (AEDT) or 04:30Z (AEST),
    # i.e. 14:30 Sydney local, and same calendar day as event_date.
    parsed = datetime.strptime(event_dt, "%Y-%m-%d %H:%M:%S %z")
    assert parsed.utcoffset().total_seconds() == 0
    assert parsed.strftime("%Y-%m-%d") == d
    assert (parsed.hour, parsed.minute) in {(3, 30), (4, 30)}
