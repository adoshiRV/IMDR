"""Tests for src/imdr/domains/econ/apra_madis.py.

No network calls -- `discover_backseries_url` is tested against a synthetic
HTML snippet mirroring the real MADIS publication page's three download
tiles (verified 2026-07-14: current-month file, current back-series file,
and a legacy pre-rename back-series file that must be excluded). The XLSX
parse layer is tested against a synthetic openpyxl workbook mirroring the
real Table 1 layout (header row 2, data from row 3, big-4 institution
names + housing owner-occ/investment columns).
"""

from __future__ import annotations

import datetime
import io

import openpyxl
import pytest

from imdr.domains.econ.apra_madis import (
    BANK_MAP,
    build_rows,
    discover_backseries_url,
    parse_backseries_rows,
    parse_backseries_xlsx,
)


_PAGE_HTML = """
<html><body>
<a class="download-tile__link" href="/system/files/2026-06/Monthly%20authorised%20deposit-taking%20institution%20statistics%20May%202026.xlsx">
  Monthly authorised deposit-taking institution statistics May 2026 XLSX 331.94 KB &middot; 30 June 2026
</a>
<a class="download-tile__link" href="/system/files/2026-06/Monthly%20authorised%20deposit-taking%20institution%20statistics%20back-series%20March%202019%20-%20May%202026.xlsx">
  Monthly authorised deposit-taking institution statistics back-series March 2019 - May 2026 XLSX 2.49 MB &middot; 30 June 2026
</a>
<a class="download-tile__link" href="/system/files/monthly_banking_statistics_june_2019_back_series.xlsx">
  Monthly banking statistics June 2019 back series XLSX 25.17 MB &middot; 8 September 2019
</a>
</body></html>
"""


class TestDiscoverBackseriesUrl:
    def test_picks_current_back_series_not_current_month_or_legacy(self) -> None:
        url = discover_backseries_url(_PAGE_HTML)
        assert url == (
            "https://www.apra.gov.au/system/files/2026-06/Monthly%20authorised%20"
            "deposit-taking%20institution%20statistics%20back-series%20March%202019"
            "%20-%20May%202026.xlsx"
        )

    def test_returns_none_when_no_matching_link(self) -> None:
        html = "<html><body><a href=\"/foo.xlsx\">Some other file</a></body></html>"
        assert discover_backseries_url(html) is None


_HEADER = [
    "Period", "ABN", "Institution Name",
    "Cash and deposits with financial institutions", "Trading securities",
    "Investment securities", "Net acceptances of customers",
    "Total residents assets", "Total securitised assets on balance sheet",
    "Loans to non-financial businesses", "Loans to financial institutions",
    "Loans to general government",
    "Loans to households: Housing: Owner-occupied",
    "Loans to households: Housing: Investment",
    "Loans to households: Credit cards", "Loans to households: Other",
    "Loans to community service organisations",
    "Total residents loans and finance leases",
]


def _data_row(period: datetime.date, abn: int, name: str, owner_occ, investor) -> tuple:
    row = [None] * len(_HEADER)
    row[0] = datetime.datetime(period.year, period.month, period.day)
    row[1] = abn
    row[2] = name
    row[12] = owner_occ
    row[13] = investor
    row[17] = (owner_occ or 0) + (investor or 0)
    return tuple(row)


def _raw_rows() -> list[tuple]:
    return [
        ("($million)",) + (None,) * (len(_HEADER) - 1),
        tuple(_HEADER),
        _data_row(datetime.date(2026, 5, 31), 11005357522,
                   "Australia and New Zealand Banking Group Limited", 216307.6, 111471.1),
        _data_row(datetime.date(2026, 5, 31), 48123123124,
                   "Commonwealth Bank of Australia", 409938.2, 220558.5),
        _data_row(datetime.date(2026, 5, 31), 999999999,
                   "Alex Bank Pty Ltd", 5.0, 0.0),
        _data_row(datetime.date(2026, 4, 30), 11005357522,
                   "Australia and New Zealand Banking Group Limited", 215000.0, 110000.0),
    ]


class TestParseBackseriesRows:
    def test_extracts_only_bank_map_institutions(self) -> None:
        parsed = parse_backseries_rows(_raw_rows())
        institutions = {p["institution"] for p in parsed}
        assert institutions == {
            "Australia and New Zealand Banking Group Limited",
            "Commonwealth Bank of Australia",
        }
        assert len(parsed) == 3

    def test_values_and_period_extracted_correctly(self) -> None:
        parsed = parse_backseries_rows(_raw_rows())
        anz_may = next(p for p in parsed if p["institution"].startswith("Australia") and p["period"] == datetime.date(2026, 5, 31))
        assert anz_may["owner_occ"] == 216307.6
        assert anz_may["investor"] == 111471.1

    def test_missing_header_column_raises(self) -> None:
        bad_header = [h for h in _HEADER if h != "Loans to households: Housing: Investment"]
        rows = [
            ("($million)",) + (None,) * (len(bad_header) - 1),
            tuple(bad_header),
        ]
        with pytest.raises(RuntimeError, match="MADIS Table 1 header missing expected column"):
            parse_backseries_rows(rows)

    def test_missing_period_header_row_raises(self) -> None:
        with pytest.raises(RuntimeError, match="could not locate header row"):
            parse_backseries_rows([("not a header",)])


def _build_workbook_bytes() -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Table 1"
    for row in _raw_rows():
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


class TestParseBackseriesXlsx:
    def test_roundtrip_through_real_openpyxl_workbook(self) -> None:
        xlsx_bytes = _build_workbook_bytes()
        parsed = parse_backseries_xlsx(xlsx_bytes)
        assert len(parsed) == 3
        institutions = {p["institution"] for p in parsed}
        assert institutions == {
            "Australia and New Zealand Banking Group Limited",
            "Commonwealth Bank of Australia",
        }


class TestBuildRows:
    def test_emits_owner_occ_and_investor_indicators_per_bank(self) -> None:
        parsed = parse_backseries_rows(_raw_rows())
        indicators, observations = build_rows(parsed)

        codes = {i.imdr_code for i in indicators}
        assert codes == {
            "APRA.ADI.ANZ.HOUSING_OWNER_OCC.AU",
            "APRA.ADI.ANZ.HOUSING_INVESTOR.AU",
            "APRA.ADI.CBA.HOUSING_OWNER_OCC.AU",
            "APRA.ADI.CBA.HOUSING_INVESTOR.AU",
        }
        for ind in indicators:
            assert ind.category == "credit"
            assert ind.frequency == "MONTHLY"
            assert ind.unit == "aud_mn"
            assert ind.country_iso == "AU"

        anz_oo_obs = [o for o in observations if o.imdr_code == "APRA.ADI.ANZ.HOUSING_OWNER_OCC.AU"]
        assert len(anz_oo_obs) == 2
        may_obs = next(o for o in anz_oo_obs if o.obs_date == datetime.date(2026, 5, 31))
        assert may_obs.value == 216307.6

    def test_since_until_filter_observations(self) -> None:
        parsed = parse_backseries_rows(_raw_rows())
        _, observations = build_rows(parsed, since=datetime.date(2026, 5, 1))
        assert all(o.obs_date >= datetime.date(2026, 5, 1) for o in observations)
        assert len(observations) == 4  # ANZ OO+INV, CBA OO+INV, May only

    def test_bank_map_has_exactly_big_four(self) -> None:
        assert set(BANK_MAP.values()) == {"ANZ", "CBA", "NAB", "WBC"}
