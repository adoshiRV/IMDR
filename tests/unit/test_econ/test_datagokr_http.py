"""Tests for src/imdr/domains/econ/datagokr_http.py.

Network-free -- requests.Session.get is mocked throughout. Covers:
- the raw-key-in-URL gotcha (serviceKey must not be re-encoded)
- item normalisation (empty / single dict / list)
- pagination over totalCount
- resultCode != "00" raises
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from imdr.domains.econ.datagokr_http import (
    _build_url,
    _extract_items,
    fetch_datagokr_rows,
)


_ENCODED_KEY = "aqdZ8eHvJlQAgqA2OwkRokPIufG3MZi7%2F1DzofRMjTfK%2FmUNITOrY9oZFhs3S%2FSv3CjJmdd7Np6Yx6h8GYLQwQ%3D%3D"


def _envelope(items, total_count: int, result_code: str = "00") -> dict:
    body: dict = {"totalCount": total_count}
    if items is not None:
        body["items"] = {"item": items}
    else:
        body["items"] = {}
    return {
        "response": {
            "header": {"resultCode": result_code, "resultMsg": "OK" if result_code == "00" else "ERROR"},
            "body": body,
        }
    }


# ---------------------------------------------------------------------------
# _build_url — the raw-key gotcha
# ---------------------------------------------------------------------------

class TestBuildUrl:
    def test_key_is_not_re_encoded(self) -> None:
        url = _build_url("https://apis.data.go.kr/x/y/z", _ENCODED_KEY, {"basDt": "20260803"})
        # The key's own %2F / %3D sequences must survive verbatim -- a second
        # pass of urlencoding would turn "%2F" into "%252F".
        assert f"serviceKey={_ENCODED_KEY}" in url
        assert "%25" not in url

    def test_other_params_are_encoded(self) -> None:
        url = _build_url("https://apis.data.go.kr/x/y/z", "plainkey", {"basDt": "20260803", "pageNo": 1})
        assert "basDt=20260803" in url
        assert "pageNo=1" in url

    def test_params_needing_encoding_are_escaped(self) -> None:
        url = _build_url("https://apis.data.go.kr/x/y/z", "plainkey", {"isinCd": "AB/CD"})
        assert "isinCd=AB%2FCD" in url


# ---------------------------------------------------------------------------
# _extract_items — normalisation + resultCode
# ---------------------------------------------------------------------------

class TestExtractItems:
    def test_list_of_items_passthrough(self) -> None:
        items, total = _extract_items(_envelope([{"a": 1}, {"a": 2}], 2))
        assert items == [{"a": 1}, {"a": 2}]
        assert total == 2

    def test_single_dict_item_normalised_to_list(self) -> None:
        items, total = _extract_items(_envelope({"a": 1}, 1))
        assert items == [{"a": 1}]
        assert total == 1

    def test_empty_items_normalises_to_empty_list(self) -> None:
        items, total = _extract_items(_envelope(None, 0))
        assert items == []
        assert total == 0

    def test_result_code_not_00_raises(self) -> None:
        with pytest.raises(RuntimeError, match="resultCode='99'"):
            _extract_items(_envelope([], 0, result_code="99"))


# ---------------------------------------------------------------------------
# fetch_datagokr_rows — pagination
# ---------------------------------------------------------------------------

class TestFetchDatagokrRowsPagination:
    def test_pages_until_total_count_reached(self) -> None:
        page1 = [{"isinCd": f"ISIN{i}"} for i in range(3)]
        page2 = [{"isinCd": f"ISIN{i}"} for i in range(3, 5)]
        responses = [
            MagicMock(json=lambda p=page1: _envelope(p, 5)),
            MagicMock(json=lambda p=page2: _envelope(p, 5)),
        ]
        for r in responses:
            r.raise_for_status = MagicMock()

        session = MagicMock()
        session.get = MagicMock(side_effect=responses)

        with patch("imdr.domains.econ.datagokr_http.time.sleep"):
            rows = fetch_datagokr_rows(session, "https://apis.data.go.kr/x/y/z", "key",
                                        {}, page_size=3)

        assert len(rows) == 5
        assert session.get.call_count == 2

    def test_single_page_when_total_fits(self) -> None:
        page1 = [{"isinCd": "A"}, {"isinCd": "B"}]
        resp = MagicMock(json=lambda: _envelope(page1, 2))
        resp.raise_for_status = MagicMock()
        session = MagicMock()
        session.get = MagicMock(return_value=resp)

        rows = fetch_datagokr_rows(session, "https://apis.data.go.kr/x/y/z", "key",
                                    {}, page_size=1000)
        assert rows == page1
        assert session.get.call_count == 1

    def test_empty_first_page_stops_immediately(self) -> None:
        resp = MagicMock(json=lambda: _envelope(None, 0))
        resp.raise_for_status = MagicMock()
        session = MagicMock()
        session.get = MagicMock(return_value=resp)

        rows = fetch_datagokr_rows(session, "https://apis.data.go.kr/x/y/z", "key", {})
        assert rows == []
        assert session.get.call_count == 1

    def test_max_pages_caps_requests(self) -> None:
        page = [{"isinCd": "A"}]
        resp = MagicMock(json=lambda: _envelope(page, 100))
        resp.raise_for_status = MagicMock()
        session = MagicMock()
        session.get = MagicMock(return_value=resp)

        with patch("imdr.domains.econ.datagokr_http.time.sleep"):
            rows = fetch_datagokr_rows(session, "https://apis.data.go.kr/x/y/z", "key",
                                        {}, page_size=1, max_pages=3)
        assert session.get.call_count == 3
        assert len(rows) == 3
