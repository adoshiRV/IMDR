"""Tests for src/imdr/domains/econ/sqm_research.py parse + transform layer.

No network calls — we construct minimal synthetic HTML snippets that mirror
the real SQM Research DOM structure (verified 2026-07-14, see the module
docstring) and feed synthetic JSON points directly into the pure transform
functions.

Covered:
- _extract_data_array pulls the embedded `var data = [...]` JSON literal
  out of a page, and returns [] when the script is absent.
- rent_points_to_rows builds the 3 series (combined/house/unit) per city,
  applies the since/until window, and skips points with a null field.
- vacancy_points_to_rows builds one series per city (or National when
  city is None), converts the vr fraction to a percent, and derives
  obs_date as the first of the {year, month}.
"""

from __future__ import annotations

import datetime

from imdr.domains.econ.sqm_research import (
    _extract_data_array,
    rent_points_to_rows,
    vacancy_points_to_rows,
)


def _rent_page(data_json: str) -> str:
    return f"""
    <html><body>
    <table class="table custom-table tbl-small"><tbody><tr><td>Sydney</td></tr></tbody></table>
    <script>
        var houses_all = data.map(item => [item.date, parseInt(item.houses_all, 10)]);
        var data = {data_json};
    </script>
    </body></html>
    """


class TestExtractDataArray:
    def test_extracts_embedded_json_array(self) -> None:
        html = _rent_page(
            '[{"date":"2026-07-01","houses_all":1159.63,"houses_3":1068.7,'
            '"units_all":757.06,"units_2":773.64,"combined":920.44}]'
        )
        points = _extract_data_array(html)
        assert points == [{
            "date": "2026-07-01", "houses_all": 1159.63, "houses_3": 1068.7,
            "units_all": 757.06, "units_2": 773.64, "combined": 920.44,
        }]

    def test_returns_empty_list_when_script_absent(self) -> None:
        html = "<html><body><h1>No chart here</h1></body></html>"
        assert _extract_data_array(html) == []


class TestRentPointsToRows:
    _POINTS = [
        {"date": "2026-06-15", "houses_all": 1160.51, "houses_3": 1074.81,
         "units_all": 760.25, "units_2": 774.58, "combined": 922.68},
        {"date": "2026-07-01", "houses_all": 1159.63, "houses_3": 1068.7,
         "units_all": 757.06, "units_2": 773.64, "combined": 920.44},
        {"date": "2026-07-08", "houses_all": 1149.81, "houses_3": 1063.85,
         "units_all": 757.53, "units_2": 772.82, "combined": 916.73},
    ]

    def test_builds_combined_house_unit_series_per_city(self) -> None:
        indicators, observations = rent_points_to_rows("SYDNEY", self._POINTS)
        codes = {i.imdr_code for i in indicators}
        assert codes == {
            "SQM.RENT.SYDNEY.AU",
            "SQM.RENT.SYDNEY_HOUSE.AU",
            "SQM.RENT.SYDNEY_UNIT.AU",
        }
        assert len(observations) == 3 * len(self._POINTS)
        combined_latest = next(
            o for o in observations
            if o.imdr_code == "SQM.RENT.SYDNEY.AU" and o.obs_date == datetime.date(2026, 7, 8)
        )
        assert combined_latest.value == 916.73

    def test_indicator_metadata(self) -> None:
        indicators, _ = rent_points_to_rows("MELBOURNE", self._POINTS)
        house = next(i for i in indicators if i.imdr_code == "SQM.RENT.MELBOURNE_HOUSE.AU")
        assert house.frequency == "WEEKLY"
        assert house.category == "housing"
        assert house.country_iso == "AU"
        assert house.unit == "aud_pw"
        assert house.vendor_name == "SQM Research"

    def test_since_until_window_filters_observations(self) -> None:
        _, observations = rent_points_to_rows(
            "SYDNEY", self._POINTS,
            since=datetime.date(2026, 7, 1), until=datetime.date(2026, 7, 1),
        )
        obs_dates = {o.obs_date for o in observations}
        assert obs_dates == {datetime.date(2026, 7, 1)}

    def test_skips_points_with_null_field(self) -> None:
        points = [{"date": "2026-07-01", "houses_all": None, "houses_3": 1.0,
                   "units_all": 2.0, "units_2": 3.0, "combined": 4.0}]
        _, observations = rent_points_to_rows("PERTH", points)
        house_obs = [o for o in observations if o.imdr_code == "SQM.RENT.PERTH_HOUSE.AU"]
        assert house_obs == []
        combined_obs = [o for o in observations if o.imdr_code == "SQM.RENT.PERTH.AU"]
        assert len(combined_obs) == 1


class TestVacancyPointsToRows:
    _POINTS = [
        {"year": 2026, "month": 5, "properties": "746151", "listings": 10820, "vr": "0.0145"},
        {"year": 2026, "month": 6, "properties": "746978", "listings": 11957, "vr": "0.0160"},
    ]

    def test_builds_one_series_per_city(self) -> None:
        indicators, observations = vacancy_points_to_rows("SYDNEY", "SYDNEY", self._POINTS)
        assert len(indicators) == 1
        assert indicators[0].imdr_code == "SQM.VACANCY.SYDNEY.AU"
        assert indicators[0].frequency == "MONTHLY"
        assert indicators[0].unit == "pct"
        latest = next(o for o in observations if o.obs_date == datetime.date(2026, 6, 1))
        assert round(latest.value, 2) == 1.60

    def test_national_uses_national_label_and_code(self) -> None:
        indicators, _ = vacancy_points_to_rows("NATIONAL", None, self._POINTS)
        assert indicators[0].imdr_code == "SQM.VACANCY.NATIONAL.AU"
        assert "National" in indicators[0].display_name

    def test_obs_date_is_first_of_month(self) -> None:
        _, observations = vacancy_points_to_rows("PERTH", "PERTH", self._POINTS)
        obs_dates = sorted(o.obs_date for o in observations)
        assert obs_dates == [datetime.date(2026, 5, 1), datetime.date(2026, 6, 1)]

    def test_since_until_window_filters_observations(self) -> None:
        _, observations = vacancy_points_to_rows(
            "PERTH", "PERTH", self._POINTS,
            since=datetime.date(2026, 6, 1), until=datetime.date(2026, 6, 30),
        )
        assert len(observations) == 1
        assert observations[0].obs_date == datetime.date(2026, 6, 1)

    def test_skips_points_with_null_vr(self) -> None:
        points = [{"year": 2026, "month": 6, "properties": "1", "listings": 2, "vr": None}]
        _, observations = vacancy_points_to_rows("HOBART", "HOBART", points)
        assert observations == []
