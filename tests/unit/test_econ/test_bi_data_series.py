"""Tests for BI's per-edition data-series archives (PMI, Survei Perbankan).

Covers `src/imdr/domains/econ/bi_survey.py`'s discovery + forecast-guard
layer and the two fetchers built on it
(`scripts/econ/id/bi/bi_pmi.py`, `bi_bank_survey.py`).

No network. The XLSX fixtures are built in-memory to mirror the real sheet
layout captured on 2026-09-21.

What each test pins:

- **The forecast column.** BI ships next quarter's projection inside the
  current edition, flagged with a trailing `*` in the period row
  ("Angka Perkiraan"). It parses exactly like an actual, so without a filter
  a forecast lands in `econ.fact_indicator` as a print — and is never
  corrected, because the following edition writes the same period as an
  actual and the revision-aware loader reads the change as a legitimate
  vintage bump rather than a repair.
- **Discovery, not construction.** Each edition's ZIP has its own filename
  and BI is inconsistent about it, so a slug template silently goes stale.
- **The two sheets use different layouts**, and swapping them yields zero
  rows rather than an error.
"""

from __future__ import annotations

import datetime as dt

import pandas as pd
import pytest
from scripts.econ.id.bi import bi_bank_survey, bi_pmi

from imdr.domains.econ import bi_survey


def _write_sheet(path, rows: list[list], sheet: str) -> None:
    pd.DataFrame(rows).to_excel(path, sheet_name=sheet, header=False, index=False)


@pytest.fixture
def pmi_xlsx(tmp_path):
    """Mirror of `T1 - Komponen PMI`: year row 4, quarter row 5, data col 2.

    Two real years plus a starred forecast quarter, and the trailing English
    label column BI appends.
    """
    path = tmp_path / "PMI.xlsx"
    rows = [
        [None] * 8,
        [None, "TABEL 1. PROMPT MANUFACTURING INDEX"] + [None] * 6,
        [None, "(%, Indeks)"] + [None] * 6,
        [None] * 8,
        # year row: year appears once, over its first quarter
        [None, "Komponen PMI", 2025, None, None, None, 2026, "Component of PMI"],
        [None, None, "I", "II", "III", "IV", "I", None],
        [None, "Volume Produksi", 51.5, 52.0, 53.0, 54.0, 55.0, "Production"],
        [None, "PMI - BI", 48.94, 49.5, 50.0, 50.5, 51.0, "PMI - BI"],
    ]
    _write_sheet(path, rows, "T1 - Komponen PMI")
    return path


@pytest.fixture
def pmi_xlsx_with_forecast(tmp_path):
    path = tmp_path / "PMI_fc.xlsx"
    rows = [
        [None] * 8,
        [None, "TABEL 1."] + [None] * 6,
        [None, "(%, Indeks)"] + [None] * 6,
        [None] * 8,
        [None, "Komponen PMI", 2026, None, None, None, None, "Component of PMI"],
        # Q3 is BI's projection for the coming quarter.
        [None, None, "I", "II", "III*", None, None, None],
        [None, "PMI - BI", 52.03, 51.43, 52.32, None, None, "PMI - BI"],
    ]
    _write_sheet(path, rows, "T1 - Komponen PMI")
    return path


# ---------------------------------------------------------------------------
# forecast_periods
# ---------------------------------------------------------------------------

def test_forecast_periods_flags_starred_quarter(pmi_xlsx_with_forecast):
    got = bi_survey.forecast_periods(
        pmi_xlsx_with_forecast, "T1 - Komponen PMI",
        year_row=4, month_row=5, first_data_col=2,
    )
    assert got == {dt.date(2026, 7, 1)}


def test_forecast_periods_empty_when_nothing_starred(pmi_xlsx):
    got = bi_survey.forecast_periods(
        pmi_xlsx, "T1 - Komponen PMI",
        year_row=4, month_row=5, first_data_col=2,
    )
    assert got == set()


def test_forecast_period_is_parsed_as_an_actual_without_the_guard(
    pmi_xlsx_with_forecast,
):
    """The whole reason the guard exists: `III*` looks like a normal quarter.

    If this ever stops being true the guard is harmless, but the test
    documents why it is not optional.
    """
    parsed = bi_survey.parse_survey_rows(
        pmi_xlsx_with_forecast, "T1 - Komponen PMI",
        rows=[6], year_row=4, month_row=5, first_data_col=2,
    )
    dates = [d for d, v in parsed[6] if v is not None]
    assert dt.date(2026, 7, 1) in dates, "starred column no longer parses"


def test_forecast_periods_tolerates_short_sheet(tmp_path):
    path = tmp_path / "tiny.xlsx"
    _write_sheet(path, [[None, "only one row"]], "S")
    assert bi_survey.forecast_periods(
        path, "S", year_row=4, month_row=5, first_data_col=2
    ) == set()


# ---------------------------------------------------------------------------
# Fetcher target tables
# ---------------------------------------------------------------------------

def test_pmi_codes_are_unique_and_country_suffixed():
    codes = [c for _, c, _ in bi_pmi._T1_TARGETS + bi_pmi._T2_TARGETS]
    assert len(codes) == len(set(codes)) == 20
    assert all(c.startswith("BI.PMI.") and c.endswith(".ID") for c in codes)


def test_pmi_row_indices_are_unique_per_sheet():
    """A duplicated row index would silently emit the same series twice."""
    for targets in (bi_pmi._T1_TARGETS, bi_pmi._T2_TARGETS):
        rows = [r for r, _, _ in targets]
        assert len(rows) == len(set(rows))


def test_pmi_headline_is_present():
    codes = {c for _, c, _ in bi_pmi._T1_TARGETS}
    assert "BI.PMI.HEADLINE.ID" in codes


def test_bank_survey_codes_are_unique_and_complete():
    codes = [c for _, c, _ in bi_bank_survey._TARGETS]
    assert len(codes) == len(set(codes)) == 33
    assert all(c.startswith("BI.LOAN_DEMAND.") and c.endswith(".ID") for c in codes)
    assert "BI.LOAN_DEMAND.TOTAL.ID" in codes


def test_bank_survey_row_indices_are_unique():
    rows = [r for r, _, _ in bi_bank_survey._TARGETS]
    assert len(rows) == len(set(rows))


def test_the_two_fetchers_use_different_layouts():
    """Swapping them yields zero rows rather than an error, so pin both."""
    assert bi_pmi._T1_LAYOUT == {"year_row": 4, "month_row": 5, "first_data_col": 2}
    assert bi_bank_survey._LAYOUT == {
        "year_row": 2, "month_row": 3, "first_data_col": 5,
    }


def test_units_differ_between_the_two_surveys():
    """PMI is an index; Survei Perbankan is a weighted net balance in %.

    Tagging the net balance as `index` would make it look comparable to the
    PMI's 50-line, which it is not.
    """
    import inspect

    assert 'unit="index"' in inspect.getsource(bi_pmi._emit)
    assert 'unit="pct"' in inspect.getsource(bi_bank_survey.run_fetch)


def test_bank_survey_category_is_credit_not_sentiment():
    """It is bank-reported credit demand, so it belongs in the credit cell."""
    import inspect

    assert 'category="credit"' in inspect.getsource(bi_bank_survey.run_fetch)


# ---------------------------------------------------------------------------
# Discovery contract
# ---------------------------------------------------------------------------

def test_discovery_raises_when_category_has_no_editions(monkeypatch):
    """Loud failure beats an empty fetch -- a silently-zero run looks healthy."""
    monkeypatch.setattr(bi_survey, "_get_text", lambda url: "<html>nothing</html>")
    with pytest.raises(RuntimeError, match="no detail links"):
        bi_survey.discover_latest_data_series_zip("prompt manufacturing index")


def test_discovery_raises_when_edition_has_no_zip(monkeypatch):
    listing = '<a href="/id/publikasi/laporan/Pages/PMI-Tw-II-2026.aspx">PMI</a>'

    def fake_get(url: str) -> str:
        return listing if "Kategori" in url else "<html>only a pdf.pdf here</html>"

    monkeypatch.setattr(bi_survey, "_get_text", fake_get)
    with pytest.raises(RuntimeError, match=r"no \.zip attachment"):
        bi_survey.discover_latest_data_series_zip("prompt manufacturing index")


def test_discovery_returns_absolute_url_from_relative_href(monkeypatch):
    listing = '<a href="/id/publikasi/laporan/Pages/PMI-Tw-II-2026.aspx">PMI</a>'
    detail = '<a href="/id/publikasi/laporan/Documents/Data-Series-PMI-Tw-II-2026.zip">z</a>'

    def fake_get(url: str) -> str:
        return listing if "Kategori" in url else detail

    monkeypatch.setattr(bi_survey, "_get_text", fake_get)
    zip_url, detail_url = bi_survey.discover_latest_data_series_zip("x")
    assert zip_url == (
        "https://www.bi.go.id/id/publikasi/laporan/Documents/"
        "Data-Series-PMI-Tw-II-2026.zip"
    )
    assert detail_url.startswith("https://www.bi.go.id/id/publikasi/laporan/Pages/")


@pytest.mark.parametrize(
    "filename",
    [
        # Every one of these is a real BI filename for the same series.
        "Data-Series-PMI-Triwulan-II-2026.zip",
        "PMI-Triwulan-I-2026.zip",
        "Data-Series-PMI-Tw-IV-2025.zip",
        "Data-Series-Survei-Perbank-Tw-IV-2025.zip",
    ],
)
def test_discovery_accepts_bis_inconsistent_filenames(monkeypatch, filename):
    """No slug template spans these, which is why discovery is mandatory."""
    listing = '<a href="/id/publikasi/laporan/Pages/E.aspx">e</a>'
    detail = f'<a href="/id/publikasi/laporan/Documents/{filename}">z</a>'

    def fake_get(url: str) -> str:
        return listing if "Kategori" in url else detail

    monkeypatch.setattr(bi_survey, "_get_text", fake_get)
    zip_url, _ = bi_survey.discover_latest_data_series_zip("x")
    assert zip_url.endswith(filename)
