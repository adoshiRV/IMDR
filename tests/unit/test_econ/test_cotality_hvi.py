"""Tests for src/imdr/domains/econ/cotality_hvi.py parse layer.

No network calls / no Playwright — we construct minimal synthetic HTML
snippets that mirror the real Cotality DOM structure (verified 2026-07-14,
see the module docstring) and test the BeautifulSoup parse functions
directly.

Covered:
- _parse_monthly_table extracts the All Dwellings index value per region,
  correctly distinguishing the two Brisbane metro definitions.
- _parse_monthly_table skips rows whose city label is not in MONTHLY_REGION_MAP.
- _parse_month_end_date parses the "30 June 2026" caption.
- _parse_month_end_date returns None when the caption div is absent.
"""

from __future__ import annotations

from imdr.domains.econ.cotality_hvi import (
    MONTHLY_REGION_MAP,
    _parse_month_end_date,
    _parse_monthly_table,
)


def _monthly_row(city: str, all_dwellings_value: str) -> str:
    return f"""
    <tr>
        <td>{city}</td>
        <td>{all_dwellings_value}</td>
        <td style="text-align:right;">0.3%</td><td><span class="infopoint-details__icon mini arrow_upward_alt">arrow_upward_alt</span></td>
        <td style="text-align:right;">-1.2%</td><td><span class="infopoint-details__icon mini arrow_downward_alt">arrow_downward_alt</span></td>
        <td>265.7</td>
        <td style="text-align:right;">-0.1%</td><td><span class="infopoint-details__icon mini arrow_downward_alt">arrow_downward_alt</span></td>
        <td style="text-align:right;">-1.5%</td><td><span class="infopoint-details__icon mini arrow_downward_alt">arrow_downward_alt</span></td>
        <td>191.9</td>
        <td style="text-align:right;">1.1%</td><td><span class="infopoint-details__icon mini arrow_upward_alt">arrow_upward_alt</span></td>
        <td style="text-align:right;">-0.6%</td><td><span class="infopoint-details__icon mini arrow_downward_alt">arrow_downward_alt</span></td>
    </tr>
    """


def _build_monthly_page(rows: list[str], *, month_end: str | None = "30 June 2026") -> str:
    date_div = f'<div class="graph-date-month">{month_end}</div>' if month_end else ""
    rows_html = "".join(rows)
    return f"""
    <html><body>
    <h3>Cotality Daily Home Value Index</h3>
    <table><thead><tr><th>City</th></tr></thead>
      <tbody><tr><td>Sydney</td><td>240.5</td></tr></tbody>
    </table>
    <h3>Cotality Daily Home Value Index: Monthly Values*</h3>
    <div class="w-embed">
      {date_div}
      <table class="indices table-fixed">
        <thead><tr><th>City</th></tr></thead>
        <tbody class="graph-api-data">{rows_html}</tbody>
      </table>
    </div>
    </body></html>
    """


class TestParseMonthlyTable:
    def test_extracts_all_dwellings_value_per_region(self) -> None:
        html = _build_monthly_page([
            _monthly_row("Sydney", "241.6"),
            _monthly_row("Darwin", "133.4"),
        ])
        values = _parse_monthly_table(html)
        assert values == {"sydney": 241.6, "darwin": 133.4}

    def test_distinguishes_the_two_brisbane_metro_definitions(self) -> None:
        html = _build_monthly_page([
            _monthly_row("Brisbane (inc Gold Coast)", "235"),
            _monthly_row("Brisbane", "234.1"),
        ])
        values = _parse_monthly_table(html)
        assert values["brisbane (inc gold coast)"] == 235.0
        assert values["brisbane"] == 234.1
        assert MONTHLY_REGION_MAP["brisbane (inc gold coast)"][0] == "BRISBANE"
        assert MONTHLY_REGION_MAP["brisbane"][0] == "BRISBANE_GCCSA"

    def test_skips_unrecognised_city_label(self) -> None:
        html = _build_monthly_page([
            _monthly_row("Wollongong", "150.0"),
            _monthly_row("Hobart", "209.4"),
        ])
        values = _parse_monthly_table(html)
        assert "wollongong" not in values
        assert values["hobart"] == 209.4

    def test_returns_empty_dict_when_monthly_table_absent(self) -> None:
        html = "<html><body><h3>Some other page</h3></body></html>"
        assert _parse_monthly_table(html) == {}


class TestParseMonthEndDate:
    def test_parses_caption_date(self) -> None:
        html = _build_monthly_page([_monthly_row("Sydney", "241.6")])
        result = _parse_month_end_date(html)
        assert result is not None
        assert result.isoformat() == "2026-06-30"

    def test_returns_none_when_caption_absent(self) -> None:
        html = _build_monthly_page([_monthly_row("Sydney", "241.6")], month_end=None)
        assert _parse_month_end_date(html) is None
