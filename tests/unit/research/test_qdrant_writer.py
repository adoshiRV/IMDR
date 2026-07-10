"""Unit tests for QdrantWriter.search() filter construction.

Regression cover for the 2026-06-23 date-filter fix: a `publish_date`
gte/lte range must build a Qdrant ``DatetimeRange`` (it is an ISO date
string), NOT a numeric ``Range`` (which raised
"Input should be a valid number" on the string), and the writer must
lazily create the ``datetime`` payload index that range needs to match.

No live Qdrant — the client is mocked and we inspect the ``query_filter``
the writer hands to ``query_points``.
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

# playground/research is the import root for the research ingest package
_RESEARCH_ROOT = Path(__file__).resolve().parents[3] / "playground" / "research"
if str(_RESEARCH_ROOT) not in sys.path:
    sys.path.insert(0, str(_RESEARCH_ROOT))

from ingest.qdrant_writer import (  # noqa: E402
    _DATETIME_PAYLOAD_FIELDS,
    QdrantWriter,
)
from qdrant_client.http import models as qm  # noqa: E402


def _writer_with_mock_client() -> QdrantWriter:
    """Build a QdrantWriter without opening a real connection."""
    w = QdrantWriter.__new__(QdrantWriter)
    w._client = MagicMock()
    w._known_collections = set()
    w._mode = "test"
    return w


def _run_search_with_filters(filters: dict):
    w = _writer_with_mock_client()
    w.search(
        model_name="gemini-embedding-2",
        dimensions=3072,
        query_vector=[0.1, 0.2, 0.3, 0.4],
        limit=5,
        filters=filters,
    )
    assert w._client.query_points.called, "query_points was not called"
    q_filter = w._client.query_points.call_args.kwargs["query_filter"]
    conds = {c.key: c for c in q_filter.must}
    return w, conds


def test_publish_date_range_uses_datetime_range():
    w, conds = _run_search_with_filters(
        {"publish_date": {"gte": "2026-06-15", "lte": "2026-06-21"}}
    )
    cond = conds["publish_date"]
    assert isinstance(cond.range, qm.DatetimeRange), (
        "publish_date must use DatetimeRange, not numeric Range"
    )
    # DatetimeRange parses the ISO strings into datetimes (expected, correct).
    assert cond.range.gte.date().isoformat() == "2026-06-15"
    assert cond.range.lte.date().isoformat() == "2026-06-21"
    # The datetime payload index is required for the range to match anything.
    w._client.create_payload_index.assert_called_once()
    idx_kwargs = w._client.create_payload_index.call_args.kwargs
    assert idx_kwargs["field_name"] == "publish_date"
    assert idx_kwargs["field_schema"] == qm.PayloadSchemaType.DATETIME


def test_numeric_range_still_uses_plain_range():
    _, conds = _run_search_with_filters({"page_start": {"gte": 1, "lte": 5}})
    cond = conds["page_start"]
    assert isinstance(cond.range, qm.Range)
    assert not isinstance(cond.range, qm.DatetimeRange)


def test_list_filter_uses_match_any_and_scalar_uses_match_value():
    _, conds = _run_search_with_filters(
        {"vendor_code": ["jpm", "ms"], "report_id": 42}
    )
    assert isinstance(conds["vendor_code"].match, qm.MatchAny)
    assert list(conds["vendor_code"].match.any) == ["jpm", "ms"]
    assert isinstance(conds["report_id"].match, qm.MatchValue)
    assert conds["report_id"].match.value == 42


def test_no_datetime_index_created_when_no_date_filter():
    w, _ = _run_search_with_filters({"report_id": 42})
    w._client.create_payload_index.assert_not_called()


def test_publish_date_is_registered_as_a_datetime_field():
    assert "publish_date" in _DATETIME_PAYLOAD_FIELDS
