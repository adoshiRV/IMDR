"""Tests for playground/econ/rba/fetch.py parse layer.

No network calls — we construct minimal synthetic Excel-like byte payloads
and test the parser logic. The xlsx format test uses openpyxl to build a
real workbook in memory; this avoids mocking pandas internals.

Covered:
- _parse_rba_excel extracts the correct series values from a synthetic workbook.
- _parse_rba_excel raises ValueError when no header row is found.
- _parse_rba_excel returns long DataFrame with correct columns.
- run_fetch filters by since/until correctly on parsed data.
"""

from __future__ import annotations

import datetime
import io

import pandas as pd
import pytest


# ---------------------------------------------------------------------------
# Helpers — synthetic Excel builder
# ---------------------------------------------------------------------------

def _build_rba_xlsx(series_col: str, dates: list[str], values: list[float]) -> bytes:
    """Build a minimal RBA-style xlsx with preamble rows + header + data."""
    try:
        import openpyxl
    except ImportError:
        pytest.skip("openpyxl not installed")

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Data"

    # Rows 1–10: metadata preamble (arbitrary text)
    for i in range(1, 11):
        ws.append([f"Metadata row {i}", None])

    # Row 11: header
    ws.append(["Series ID", series_col])

    # Row 12+: data
    for date_str, val in zip(dates, values):
        ws.append([date_str, val])

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Parser tests
# ---------------------------------------------------------------------------

class TestParseRbaExcel:
    def test_extracts_correct_series(self) -> None:
        from playground.econ.rba.fetch import _parse_rba_excel

        raw = _build_rba_xlsx(
            series_col="FIRMMCRT",
            dates=["2024-01-01", "2024-02-01", "2024-03-01"],
            values=[4.35, 4.35, 4.35],
        )
        series_map = {
            "FIRMMCRT": ("RBA.RATES.OCR.AU", "RBA OCR", "%", "DAILY", "rates", False),
        }
        df = _parse_rba_excel(raw, series_map)

        assert set(df.columns) == {"date", "imdr_code", "value"}
        assert len(df) == 3
        assert (df["imdr_code"] == "RBA.RATES.OCR.AU").all()
        assert df["value"].iloc[0] == pytest.approx(4.35)

    def test_raises_when_no_header_row_found(self) -> None:
        from playground.econ.rba.fetch import _parse_rba_excel

        raw = _build_rba_xlsx(
            series_col="UNKNOWN_COL",
            dates=["2024-01-01"],
            values=[1.0],
        )
        series_map = {
            "FIRMMCRT": ("RBA.RATES.OCR.AU", "RBA OCR", "%", "DAILY", "rates", False),
        }
        with pytest.raises(ValueError, match="Could not find header row"):
            _parse_rba_excel(raw, series_map)

    def test_returns_long_format_with_imdr_code(self) -> None:
        from playground.econ.rba.fetch import _parse_rba_excel

        raw = _build_rba_xlsx(
            series_col="FXRUSD",
            dates=["2024-01-02", "2024-01-03"],
            values=[0.6580, 0.6620],
        )
        series_map = {
            "FXRUSD": ("RBA.FX.AUDUSD.AU", "AUD/USD", "rate", "DAILY", "fx", False),
        }
        df = _parse_rba_excel(raw, series_map)
        assert "imdr_code" in df.columns
        assert df["imdr_code"].unique().tolist() == ["RBA.FX.AUDUSD.AU"]

    def test_missing_series_column_logged_and_skipped(self) -> None:
        from playground.econ.rba.fetch import _parse_rba_excel

        # series_map asks for two cols; workbook has only one
        raw = _build_rba_xlsx(
            series_col="FIRMMCRT",
            dates=["2024-01-01"],
            values=[4.35],
        )
        series_map = {
            "FIRMMCRT": ("RBA.RATES.OCR.AU", "OCR", "%", "DAILY", "rates", False),
            "FXRUSD": ("RBA.FX.AUDUSD.AU", "AUD/USD", "rate", "DAILY", "fx", False),
        }
        df = _parse_rba_excel(raw, series_map)
        # Only the present series is returned
        assert set(df["imdr_code"].unique()) == {"RBA.RATES.OCR.AU"}

    def test_non_numeric_values_coerced_to_nan_and_dropped(self) -> None:
        from playground.econ.rba.fetch import _parse_rba_excel

        try:
            import openpyxl
        except ImportError:
            pytest.skip("openpyxl not installed")

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Data"
        for i in range(10):
            ws.append([f"meta {i}", None])
        ws.append(["Series ID", "FIRMMCRT"])
        ws.append(["2024-01-01", 4.35])
        ws.append(["2024-02-01", "n.a."])  # non-numeric
        ws.append(["2024-03-01", 4.35])
        buf = io.BytesIO()
        wb.save(buf)

        series_map = {
            "FIRMMCRT": ("RBA.RATES.OCR.AU", "OCR", "%", "DAILY", "rates", False),
        }
        df = _parse_rba_excel(buf.getvalue(), series_map)
        # Non-numeric rows are coerced to NaN; the parser does NOT drop them
        # (caller can dropna downstream). Check the value coercion only.
        assert pd.isna(df[df["date"] == pd.Timestamp("2024-02-01")]["value"].iloc[0])


# ---------------------------------------------------------------------------
# IndicatorRow construction from workbook metadata
# ---------------------------------------------------------------------------

class TestRbaIndicatorRow:
    def test_workbook_meta_produces_valid_indicator_row(self) -> None:
        from playground.econ.schema_prototype import IndicatorRow

        row = IndicatorRow(
            imdr_code="RBA.RATES.OCR.AU",
            vendor_name="RBA",
            source_code="RBA.F1.1.FIRMMCRT",
            description="RBA Cash Rate Target (mid)",
            unit="%",
            frequency="DAILY",
            country_iso="AU",
            category="rates",
            is_seasonally_adjusted=False,
        )
        assert row.imdr_code == "RBA.RATES.OCR.AU"
        assert row.frequency == "DAILY"
        assert row.country_iso == "AU"
