"""Tests for src/imdr/domains/econ/anz_indeed_jobads.py parse + transform layer.

No network calls — a synthetic openpyxl workbook mirrors the real ANZ-Indeed
workbook's sheet layout (verified 2026-07-14, see the module docstring), and
a synthetic HTML snippet mirrors the release-dates archive page's "Download
data" link.
"""

from __future__ import annotations

import datetime

import openpyxl
import pytest

from imdr.domains.econ.anz_indeed_jobads import (
    discover_download_url,
    parse_data_sheet,
    rows_to_records,
)


def _release_dates_html(*, download_href: str | None) -> str:
    link = (
        f'<p><b><u><a href="{download_href}">Download data</a></u></b></p>'
        if download_href else ""
    )
    return f"<html><body>{link}</body></html>"


class TestDiscoverDownloadUrl:
    def test_extracts_relative_link_and_makes_absolute(self) -> None:
        html = _release_dates_html(
            download_href="/content/dam/anzcomau/mediacentre/pdfs/jobads/2026/july/ANZ-Indeed%20Australian%20Job%20Ads%20data_Jun26.xlsx"
        )
        url = discover_download_url(html)
        assert url == (
            "https://www.anz.com.au/content/dam/anzcomau/mediacentre/pdfs/"
            "jobads/2026/july/ANZ-Indeed%20Australian%20Job%20Ads%20data_Jun26.xlsx"
        )

    def test_extracts_absolute_link_unchanged(self) -> None:
        html = _release_dates_html(
            download_href="https://www.anz.com.au/content/dam/anzcomau/mediacentre/pdfs/jobads/2026/july/x.xlsx"
        )
        url = discover_download_url(html)
        assert url == "https://www.anz.com.au/content/dam/anzcomau/mediacentre/pdfs/jobads/2026/july/x.xlsx"

    def test_raises_when_link_missing(self) -> None:
        html = _release_dates_html(download_href=None)
        with pytest.raises(RuntimeError, match="Download data"):
            discover_download_url(html)


def _data_workbook():
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "ANZ-Indeed Australian Job Ads"
    ws.append(["ANZ-Indeed Australian Job Ads (2019=100)"])
    ws.append([None])
    ws.append([None, "Original", "Seasonal adjusted ", "Trend"])
    ws.append([datetime.datetime(2026, 5, 1), 113.8, 116.0, 115.5])
    ws.append([datetime.datetime(2026, 6, 1), 115.0, 115.8, 116.0])
    ws.append(["Source: ANZ-Indeed Australian Job Ads"])
    return wb


class TestParseDataSheet:
    def test_extracts_date_rows_only(self) -> None:
        rows = parse_data_sheet(_data_workbook())
        assert len(rows) == 2
        assert rows[0]["date"] == datetime.date(2026, 5, 1)
        assert rows[0]["original"] == 113.8
        assert rows[0]["sa"] == 116.0
        assert rows[0]["trend"] == 115.5

    def test_skips_header_and_footer_rows(self) -> None:
        rows = parse_data_sheet(_data_workbook())
        dates = {r["date"] for r in rows}
        assert dates == {datetime.date(2026, 5, 1), datetime.date(2026, 6, 1)}


class TestRowsToRecords:
    def test_builds_three_variants(self) -> None:
        raw = parse_data_sheet(_data_workbook())
        indicators, observations = rows_to_records(raw)
        codes = {i.imdr_code for i in indicators}
        assert codes == {
            "ANZ.JOBADS.INDEX.NATIONAL.AU",
            "ANZ.JOBADS.INDEX_TREND.NATIONAL.AU",
            "ANZ.JOBADS.INDEX_ORIG.NATIONAL.AU",
        }
        assert len(observations) == 6

    def test_sa_values_correct(self) -> None:
        raw = parse_data_sheet(_data_workbook())
        _, observations = rows_to_records(raw)
        sa_obs = [o for o in observations if o.imdr_code == "ANZ.JOBADS.INDEX.NATIONAL.AU"]
        latest = next(o for o in sa_obs if o.obs_date == datetime.date(2026, 6, 1))
        assert latest.value == 115.8

    def test_indicator_metadata(self) -> None:
        raw = parse_data_sheet(_data_workbook())
        indicators, _ = rows_to_records(raw)
        sa = next(i for i in indicators if i.imdr_code == "ANZ.JOBADS.INDEX.NATIONAL.AU")
        trend = next(i for i in indicators if i.imdr_code == "ANZ.JOBADS.INDEX_TREND.NATIONAL.AU")
        orig = next(i for i in indicators if i.imdr_code == "ANZ.JOBADS.INDEX_ORIG.NATIONAL.AU")
        assert sa.category == "labour"
        assert sa.frequency == "MONTHLY"
        assert sa.country_iso == "AU"
        assert sa.unit == "index"
        assert sa.is_seasonally_adjusted is True
        assert trend.is_seasonally_adjusted is False
        assert orig.is_seasonally_adjusted is False

    def test_since_until_window_filters_observations(self) -> None:
        raw = parse_data_sheet(_data_workbook())
        _, observations = rows_to_records(
            raw, since=datetime.date(2026, 6, 1), until=datetime.date(2026, 6, 30),
        )
        obs_dates = {o.obs_date for o in observations}
        assert obs_dates == {datetime.date(2026, 6, 1)}

    def test_none_values_skipped(self) -> None:
        raw = [{"date": datetime.date(2026, 6, 1), "original": None, "sa": 115.8, "trend": None}]
        indicators, observations = rows_to_records(raw)
        codes = {i.imdr_code for i in indicators}
        assert codes == {"ANZ.JOBADS.INDEX.NATIONAL.AU"}
        assert len(observations) == 1
