"""Tests for src/imdr/domains/econ/nsdl_fpi.py (export-parser layer).

No network calls / no Playwright / no CDP-attach.

``tests/unit/test_econ/fixtures/nsdl_current_month_trimmed.xls`` is a
REAL, trimmed export (2 trading days, 01-Jul-2026 + 02-Jul-2026, plus the
trailing blank-spacer + "Note" disclaimer rows NSDL appends) sliced
directly from an actual "Export to Excel" download via BeautifulSoup
(see playground/econ/in/nsdl/trim_export_fixture.py) — not hand-authored
synthetic markup, so the rowspan/text quirks (incl. the AIFs-group's
rowspan over-reaching onto the grand Total row) are the vendor's real
ones. Small hand-built DataFrames cover edge cases the 2-day fixture
doesn't naturally exercise (malformed rows, unrecognised labels).
"""

from __future__ import annotations

import datetime
from pathlib import Path

import pandas as pd
import pytest

from imdr.domains.econ.nsdl_fpi import (
    ASSET_CLASS_MAP,
    build_indicator_rows,
    coerce_conversion,
    coerce_date,
    coerce_float,
    load_export_tables,
    parse_cash_table,
    subtotal_rows,
)

_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "nsdl_current_month_trimmed.xls"


def _df(rows: list[list[str | None]]) -> pd.DataFrame:
    """Build a small DataFrame mirroring the export's shape (>= 9 columns,
    positional access only -- parse_cash_table never reads column names)."""
    padded = [list(r) + [None] * (9 - len(r)) for r in rows]
    return pd.DataFrame(padded)


class TestCoerceHelpers:
    def test_coerce_float_handles_commas_and_negatives(self) -> None:
        assert coerce_float("1,234.56") == 1234.56
        assert coerce_float("-2521.10") == -2521.10
        assert coerce_float("") is None
        assert coerce_float("-") is None
        assert coerce_float(None) is None

    def test_coerce_float_handles_parenthesised_negative(self) -> None:
        assert coerce_float("(263.07)") == -263.07

    def test_coerce_conversion_strips_rs_prefix(self) -> None:
        assert coerce_conversion("Rs.95.8336") == 95.8336
        assert coerce_conversion(" Rs.94.5975") == 94.5975
        assert coerce_conversion("rs. 94.5975") == 94.5975

    def test_coerce_conversion_handles_bare_number(self) -> None:
        assert coerce_conversion("95.8336") == 95.8336

    def test_coerce_conversion_none_on_blank(self) -> None:
        assert coerce_conversion("") is None
        assert coerce_conversion(None) is None

    def test_coerce_date_parses_dd_mon_yyyy(self) -> None:
        assert coerce_date("14-Jul-2026") == datetime.date(2026, 7, 14)

    def test_coerce_date_none_on_blank(self) -> None:
        assert coerce_date("") is None
        assert coerce_date(None) is None


class TestParseCashTableEdgeCases:
    def test_skips_rows_with_unparsable_date(self, capsys) -> None:
        df = _df([
            ["01-Jul-2026", "Equity", "Sub-total", "1", "2", "3", "4", "Rs.95.0"],
            [None, None, None, None, None, None, None, None],  # blank spacer row
            ["Note", "Note", "Note", "Note", "Note", "Note", "Note", "Note"],  # disclaimer row
        ])
        rows = parse_cash_table(df)
        assert len(rows) == 1
        captured = capsys.readouterr()
        assert "unparsable reporting date" in captured.out

    def test_skips_rows_with_unrecognised_asset_class(self, capsys) -> None:
        df = _df([
            ["01-Jul-2026", "Equity", "Sub-total", "1", "2", "3", "4", "Rs.95.0"],
            ["01-Jul-2026", "Sectoral Breakup", "Sub-total", "1", "2", "3", "4", "Rs.95.0"],
        ])
        rows = parse_cash_table(df)
        assert len(rows) == 1
        captured = capsys.readouterr()
        assert "asset-class/route" in captured.out
        assert "Sectoral Breakup" in captured.out

    def test_skips_mutual_funds_scheme_type_rows(self) -> None:
        df = _df([
            ["01-Jul-2026", "Mutual Funds", "Equity schemes", "1", "2", "3", "4", "Rs.95.0"],
            ["01-Jul-2026", "Mutual Funds", "Debt schemes", "1", "2", "3", "4", "Rs.95.0"],
            ["01-Jul-2026", "Mutual Funds", "Sub-total", "5", "6", "7", "8", "Rs.95.0"],
        ])
        rows = parse_cash_table(df)
        assert len(rows) == 1
        assert rows[0].route == "SUBTOTAL"
        assert rows[0].net_inr_cr == 7.0

    def test_no_bare_debt_alias(self) -> None:
        # A bare "Debt" label (unconfirmed on the real export) must NOT be
        # folded into DEBT_GENERAL -- that would silently corrupt the
        # General-Limit series with an aggregate Debt number.
        assert "debt" not in ASSET_CLASS_MAP

    def test_grand_total_row_ignores_its_asset_class_column(self) -> None:
        """The confirmed live quirk: route == "Total" rows carry whatever
        asset class the vendor's rowspan last inherited (AIFs on both
        observed exports) -- that column must be IGNORED; route=="Total"
        is the authoritative signal for the grand-total row."""
        df = _df([
            ["01-Jul-2026", "AIFs", "Total", "12384.55", "15357.27", "(2972.72)", "(310.20)", "Rs.95.8336"],
        ])
        rows = parse_cash_table(df)
        assert len(rows) == 1
        assert rows[0].asset_class == "TOTAL"
        assert rows[0].route == "SUBTOTAL"
        assert rows[0].net_inr_cr == -2972.72
        assert rows[0].net_usd_mn == -310.20


class TestParseCashTableRealFixture:
    """End-to-end against the real, trimmed 2-day export fixture."""

    def _load(self):
        cash_df, deriv_df = load_export_tables(_FIXTURE)
        return cash_df, deriv_df

    def test_load_export_tables_finds_both_tables(self) -> None:
        cash_df, deriv_df = self._load()
        assert len(cash_df) > 0
        assert len(deriv_df) > 0

    def test_parses_both_days_all_8_asset_classes(self) -> None:
        cash_df, _ = self._load()
        rows = parse_cash_table(cash_df)
        st = subtotal_rows(rows)
        dates = sorted({r.reporting_date for r in rows})
        assert dates == [datetime.date(2026, 7, 1), datetime.date(2026, 7, 2)]

        by_date = {}
        for r in st:
            by_date.setdefault(r.reporting_date, set()).add(r.asset_class)
        for d in dates:
            assert by_date[d] == {
                "EQUITY", "DEBT_GENERAL", "DEBT_VRR", "DEBT_FAR", "HYBRID",
                "MUTUAL_FUNDS", "AIF", "TOTAL",
            }, f"missing asset class(es) on {d}"

    def test_aif_and_total_not_conflated_on_either_day(self) -> None:
        """Regression test for the confirmed live mis-mapping bug: AIF's
        real Sub-total and the grand Total row must resolve as separate,
        correctly-attributed rows -- no double-counting, no missing TOTAL."""
        cash_df, _ = self._load()
        rows = parse_cash_table(cash_df)
        st = subtotal_rows(rows)

        for d in (datetime.date(2026, 7, 1), datetime.date(2026, 7, 2)):
            aif_rows = [r for r in st if r.asset_class == "AIF" and r.reporting_date == d]
            total_rows = [r for r in st if r.asset_class == "TOTAL" and r.reporting_date == d]
            assert len(aif_rows) == 1, f"AIF double-counted or missing on {d}"
            assert len(total_rows) == 1, f"TOTAL double-counted or missing on {d}"

        # 01-Jul-2026 real confirmed values (from the un-trimmed source file).
        jul1_aif = next(r for r in st if r.asset_class == "AIF" and r.reporting_date == datetime.date(2026, 7, 1))
        jul1_total = next(r for r in st if r.asset_class == "TOTAL" and r.reporting_date == datetime.date(2026, 7, 1))
        assert jul1_aif.net_inr_cr == 0.0
        assert jul1_aif.net_usd_mn == 0.0
        assert jul1_total.net_inr_cr == 552.98
        assert jul1_total.net_usd_mn == 58.46
        assert jul1_total.usd_inr_conversion == 94.5975

    def test_build_indicator_rows_emits_33_indicators_and_per_day_conversion(self) -> None:
        cash_df, _ = self._load()
        rows = parse_cash_table(cash_df)
        indicators, observations = build_indicator_rows(rows)
        assert len(indicators) == 33

        conv_obs = [o for o in observations if o.imdr_code == "INDIA.NSDL.FPI.USDINR_CONVERSION.IN"]
        # 2 distinct trading days in the fixture -> 2 conversion observations,
        # NOT 1 (an earlier single-day version only emitted the first day's
        # rate, which is wrong once the export covers multiple days).
        assert len(conv_obs) == 2
        by_date = {o.obs_date: o.value for o in conv_obs}
        assert by_date[datetime.date(2026, 7, 1)] == 94.5975
        assert by_date[datetime.date(2026, 7, 2)] == 94.7323

        # 8 asset classes x 4 measures x 2 days = 64 flow observations + 2
        # conversion observations.
        assert len(observations) == 64 + 2


class TestLoadExportTables:
    def test_raises_when_fewer_than_2_tables(self, tmp_path) -> None:
        html = "<html><body><table><tr><td>only one table</td></tr></table></body></html>"
        path = tmp_path / "single_table.xls"
        path.write_text(html, encoding="utf-8")
        with pytest.raises(RuntimeError, match="Expected 2 tables"):
            load_export_tables(path)
