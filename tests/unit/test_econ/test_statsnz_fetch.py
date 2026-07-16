"""Tests for playground/econ/statsnz/fetch.py parse layer.

No network calls. Stats NZ moved from a JSON Infoshare response to the
Infoshare-format CSV (Series_Reference / Period `YYYY.MM` = quarter-end month /
Data_Value / Status Code / Type / Description); these cover the current
`parse_infoshare_csv` + `_period_to_date` + `_safe_imdr_code` layer.

Covered:
- Period `YYYY.MM` parsed to the quarter-END date.
- December period maps to 31 Dec.
- Numeric values extracted; NA / empty handled without raising.
- is_preliminary derived from Status Code (FINAL vs not).
- One IndicatorRow per distinct Description; imdr_code carries the prefix.
- Rows with an unparseable period are skipped, not fatal.
"""

from __future__ import annotations

import datetime

from playground.econ.statsnz.fetch import (
    parse_infoshare_csv,
    _period_to_date,
    _safe_imdr_code,
)

_HEADER = "Series_Reference,Period,Data_Value,Status Code,Type,Group,Description"


def _csv(*rows: str) -> str:
    return "\n".join([_HEADER, *rows]) + "\n"


class TestPeriodToDate:
    def test_march_quarter_maps_to_month_end(self) -> None:
        assert _period_to_date("2024.03") == datetime.date(2024, 3, 31)

    def test_december_quarter_maps_to_year_end(self) -> None:
        assert _period_to_date("2024.12") == datetime.date(2024, 12, 31)

    def test_june_quarter_maps_to_june_30(self) -> None:
        assert _period_to_date("2026.06") == datetime.date(2026, 6, 30)


class TestSafeImdrCode:
    def test_prefix_and_country_wrap_the_slug(self) -> None:
        code = _safe_imdr_code("CPI", "All groups", "NZ")
        assert code.startswith("STATSNZ.CPI.")
        assert code.endswith(".NZ")

    def test_non_alphanumeric_collapsed_to_single_underscore(self) -> None:
        code = _safe_imdr_code("CPI", "Food & non-alcoholic beverages", "NZ")
        slug = code[len("STATSNZ.CPI.") : -len(".NZ")]
        assert "__" not in slug


class TestParseInfoshareCsv:
    def test_indicator_and_observation_built(self) -> None:
        text = _csv("CPIQ.SE9A,2024.03,1054.0,FINAL,Index,CPI,All groups")
        indicators, obs = parse_infoshare_csv(text)
        assert len(indicators) == 1
        assert len(obs) == 1
        assert indicators[0].source_code == "CPIQ.SE9A"
        assert indicators[0].vendor_name == "STATSNZ"
        assert obs[0].obs_date == datetime.date(2024, 3, 31)
        assert obs[0].value == 1054.0

    def test_na_and_empty_values_become_none(self) -> None:
        text = _csv(
            "CPIQ.A,2024.03,NA,FINAL,Index,CPI,All groups",
            "CPIQ.B,2024.03,,FINAL,Index,CPI,Food",
        )
        _, obs = parse_infoshare_csv(text)
        assert [o.value for o in obs] == [None, None]

    def test_status_code_drives_is_preliminary(self) -> None:
        text = _csv(
            "CPIQ.A,2024.03,1.0,FINAL,Index,CPI,All groups",
            "CPIQ.B,2024.03,2.0,PROVISIONAL,Index,CPI,Food",
        )
        _, obs = parse_infoshare_csv(text)
        by_val = {o.value: o.is_preliminary for o in obs}
        assert by_val[1.0] is False
        assert by_val[2.0] is True

    def test_one_indicator_per_description(self) -> None:
        # Two periods of the same series -> one indicator, two observations.
        text = _csv(
            "CPIQ.A,2024.03,1054.0,FINAL,Index,CPI,All groups",
            "CPIQ.A,2023.12,1050.0,FINAL,Index,CPI,All groups",
        )
        indicators, obs = parse_infoshare_csv(text)
        assert len(indicators) == 1
        assert len(obs) == 2

    def test_bad_period_row_skipped(self) -> None:
        text = _csv(
            "CPIQ.A,not-a-period,1.0,FINAL,Index,CPI,All groups",
            "CPIQ.B,2024.03,2.0,FINAL,Index,CPI,Food",
        )
        _, obs = parse_infoshare_csv(text)
        assert len(obs) == 1
        assert obs[0].value == 2.0

    def test_blank_series_reference_skipped(self) -> None:
        text = _csv(",2024.03,1.0,FINAL,Index,CPI,All groups")
        indicators, obs = parse_infoshare_csv(text)
        assert indicators == []
        assert obs == []

    def test_imdr_prefix_and_category_are_honoured(self) -> None:
        text = _csv("PPIQ.X,2024.03,500.0,FINAL,Index,PPI,Outputs")
        indicators, _ = parse_infoshare_csv(
            text, imdr_prefix="PPI", country="NZ", category="other"
        )
        assert indicators[0].imdr_code.startswith("STATSNZ.PPI.")
        assert indicators[0].category == "other"
