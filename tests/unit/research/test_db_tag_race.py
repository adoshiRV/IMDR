"""Race-safety tests for research.dim_tag / dim_embedding_model upserts.

Validates that the autocommit-based upserts (``_upsert_tag_autocommit``,
``ensure_model_id``) survive a concurrent insert without surfacing
IntegrityError — that's the precondition for parallel-vendor ingest.
See docs/admin/development/parallel_vendor_ingest.md Phase 1.

These tests mock the SQLAlchemy engine; no DB connection is opened.
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

from sqlalchemy.exc import IntegrityError

# playground/research is not on the package path — add it for these tests.
_RESEARCH_ROOT = Path(__file__).resolve().parents[3] / "playground" / "research"
if str(_RESEARCH_ROOT) not in sys.path:
    sys.path.insert(0, str(_RESEARCH_ROOT))

from ingest.db import (  # noqa: E402
    _upsert_tag_autocommit,
    ensure_model_id,
    resolve_tag_ids,
)


_RACE_MARKER = object()  # sentinel: "raise IntegrityError on this call"


def _mock_engine(execute_results):
    """Build a mock Engine whose .connect().execution_options() returns a
    conn whose .execute(...).first() pulls from ``execute_results`` in
    order. Each entry is either a return value or ``_RACE_MARKER`` to
    raise IntegrityError (simulating a concurrent insert).
    """
    engine = MagicMock(name="Engine")

    conn = MagicMock(name="Connection")
    results_iter = iter(execute_results)

    def _execute(*args, **kwargs):
        result = next(results_iter)
        if result is _RACE_MARKER:
            raise IntegrityError(
                statement="INSERT ...", params={}, orig=Exception("PK violation"),
            )
        exec_result = MagicMock(name="ExecuteResult")
        exec_result.first.return_value = result
        return exec_result

    conn.execute.side_effect = _execute

    raw_conn = MagicMock(name="RawConnection")
    raw_conn.execution_options.return_value = conn
    raw_conn.__enter__ = MagicMock(return_value=raw_conn)
    raw_conn.__exit__ = MagicMock(return_value=False)

    engine.connect.return_value = raw_conn
    return engine


# ── _upsert_tag_autocommit ───────────────────────────────────────────


def test_upsert_tag_returns_existing_when_select_hits():
    engine = _mock_engine([(42,)])  # first SELECT finds the row
    out = _upsert_tag_autocommit(engine, category="domain", value="MACRO")
    assert out == 42


def test_upsert_tag_returns_new_when_select_empty_then_insert():
    # SELECT misses, INSERT returns new id
    engine = _mock_engine([None, (101,)])
    out = _upsert_tag_autocommit(engine, category="domain", value="RATES")
    assert out == 101


def test_upsert_tag_recovers_from_integrityerror_race():
    # SELECT misses → INSERT races (IntegrityError) → re-SELECT finds id
    engine = _mock_engine([None, _RACE_MARKER, (77,)])
    out = _upsert_tag_autocommit(engine, category="domain", value="MACRO")
    assert out == 77


def test_upsert_tag_returns_none_when_empty_value():
    engine = _mock_engine([])
    assert _upsert_tag_autocommit(engine, category="domain", value="") is None
    assert _upsert_tag_autocommit(engine, category="", value="MACRO") is None
    assert _upsert_tag_autocommit(engine, category="   ", value="MACRO") is None


def test_upsert_tag_truncates_oversize_value():
    # Value > 50 chars should be truncated; SELECT uses truncated form.
    long_val = "X" * 200
    engine = _mock_engine([(9,)])
    out = _upsert_tag_autocommit(engine, category="domain", value=long_val)
    assert out == 9


# ── resolve_tag_ids ──────────────────────────────────────────────────


def test_resolve_tag_ids_empty_input():
    engine = _mock_engine([])
    assert resolve_tag_ids(engine, ()) == ()


def test_resolve_tag_ids_dedupes_input_keys():
    # Two identical (category, value) tuples → one upsert call → one id.
    engine = _mock_engine([(5,)])  # only one SELECT-hit expected
    out = resolve_tag_ids(
        engine, (("domain", "MACRO"), ("domain", "MACRO"))
    )
    assert out == (5,)


def test_resolve_tag_ids_dedupes_resolved_ids():
    # Two distinct inputs both resolve to the same canonical row id.
    # The (category, value) keys differ so dedup-by-key doesn't catch
    # it; the dedup-by-resolved-id branch must.
    engine = _mock_engine([(7,), (7,)])
    out = resolve_tag_ids(
        engine, (("domain", "EQUITY"), ("topic", "EQUITY"))
    )
    assert out == (7,)


def test_resolve_tag_ids_preserves_input_order():
    # First-seen wins for ordering.
    engine = _mock_engine([(11,), (22,), (33,)])
    out = resolve_tag_ids(
        engine,
        (("domain", "RATES"), ("domain", "FX"), ("domain", "MACRO")),
    )
    assert out == (11, 22, 33)


# ── ensure_model_id ──────────────────────────────────────────────────


def test_ensure_model_id_returns_existing():
    engine = _mock_engine([(3,)])
    out = ensure_model_id(
        engine,
        provider="google",
        model_name="gemini-embedding-2",
        dimensions=3072,
    )
    assert out == 3


def test_ensure_model_id_inserts_when_missing():
    engine = _mock_engine([None, (8,)])
    out = ensure_model_id(
        engine, provider="voyage", model_name="voyage-3-large", dimensions=1024,
    )
    assert out == 8


def test_ensure_model_id_recovers_from_race():
    engine = _mock_engine([None, _RACE_MARKER, (12,)])
    out = ensure_model_id(
        engine, provider="google", model_name="gemini-embedding-2", dimensions=3072,
    )
    assert out == 12
