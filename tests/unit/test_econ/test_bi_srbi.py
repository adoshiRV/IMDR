"""Unit tests for the BI SRBI auction-result parser."""

from __future__ import annotations

import datetime

from imdr.domains.econ.bi_srbi import (
    SrbiAuction,
    _parse_pct,
    _parse_tenor,
    auction_url,
    parse_srbi_page,
)


# Backwards-compatible alias for the test names below.
_auction_url = auction_url


# ---------------------------------------------------------------------------
# URL builder
# ---------------------------------------------------------------------------

def test_auction_url_uses_indonesian_month_name():
    url = _auction_url(datetime.date(2026, 6, 10))
    assert url == (
        "https://www.bi.go.id/id/publikasi/lelang/operasi-moneter/"
        "Pages/Hasil-Lelang-SRBI-10-Juni-2026.aspx"
    )


def test_auction_url_january_january_in_indonesian_is_januari():
    url = _auction_url(datetime.date(2024, 1, 5))
    assert "5-Januari-2024" in url


def test_auction_url_no_zero_pad_on_day():
    url = _auction_url(datetime.date(2024, 3, 1))
    assert "1-Maret-2024" in url
    assert "01-Maret" not in url


# ---------------------------------------------------------------------------
# Percentage parser
# ---------------------------------------------------------------------------

def test_parse_pct_handles_indonesian_comma_decimal():
    assert _parse_pct("7,20287") == 7.20287


def test_parse_pct_returns_none_for_dash():
    assert _parse_pct("-") is None


def test_parse_pct_returns_none_for_blank():
    assert _parse_pct("") is None
    assert _parse_pct("   ") is None


def test_parse_pct_returns_none_for_garbage():
    assert _parse_pct("n/a") is None


# ---------------------------------------------------------------------------
# Tenor parser
# ---------------------------------------------------------------------------

def test_parse_tenor_bilingual_label():
    res = _parse_tenor("6 Bulan (177 Hari) / 6 Months (177 days)")
    assert res == (6, 177)


def test_parse_tenor_returns_none_for_non_data():
    assert _parse_tenor("Jangka Waktu / Term") is None


def test_parse_tenor_handles_double_digit_months():
    res = _parse_tenor("12 Bulan (359 Hari) / 12 Months (359 days)")
    assert res == (12, 359)


# ---------------------------------------------------------------------------
# Page parser — minimal fixture
# ---------------------------------------------------------------------------

_FIXTURE_HTML = """
<html><body><table>
<tr><td>Tanggal Transaksi / Transaction Date</td><td>10 Juni 2026 / June 10 th 2026</td></tr>
<tr><td>Seri/ series</td><td>IDSR041226364S (reissuance)</td><td>IDSR260327364S (reissuance)</td><td>IDSR040627364S (reissuance)</td></tr>
<tr><td>Jangka Waktu / Term</td>
<td>6 Bulan (177 Hari) / 6 Months (177 days)</td>
<td>9 Bulan (289 Hari) / 9 Months (289 days)</td>
<td>12 Bulan (359 Hari) / 12 Months (359 days)</td></tr>
<tr><td>Rate Penawaran (%) / Bidding Rate (%)</td><td>7,10 - 7,75</td><td>7,25 - 7,46</td><td>7,30 - 8,65</td></tr>
<tr><td>Rata-Rata Tertimbang Penawaran (%) / Weighted Average Bidding Rate (%)</td>
<td>7,33923</td><td>7,35026</td><td>7,73579</td></tr>
<tr><td>Rata-Rata Tertimbang Pemenang (%) / Weighted Average Winner (%)</td>
<td>7,20287</td><td>7,35026</td><td>7,57301</td></tr>
</table></body></html>
"""


def test_parse_srbi_page_returns_three_tenors_with_winning_yields():
    rows = parse_srbi_page(_FIXTURE_HTML, datetime.date(2026, 6, 10))
    assert len(rows) == 3
    expected = [
        SrbiAuction(datetime.date(2026, 6, 10), 6, 177, 7.20287),
        SrbiAuction(datetime.date(2026, 6, 10), 9, 289, 7.35026),
        SrbiAuction(datetime.date(2026, 6, 10), 12, 359, 7.57301),
    ]
    assert rows == expected


def test_parse_srbi_page_returns_empty_when_no_tables():
    assert parse_srbi_page("<html><body><p>nothing here</p></body></html>",
                          datetime.date(2026, 6, 10)) == []


def test_parse_srbi_page_skips_tenor_with_dash_yield():
    html = _FIXTURE_HTML.replace("7,20287", "-")
    rows = parse_srbi_page(html, datetime.date(2026, 6, 10))
    # 6M was dashed → only 9M and 12M survive
    assert [r.tenor_months for r in rows] == [9, 12]
