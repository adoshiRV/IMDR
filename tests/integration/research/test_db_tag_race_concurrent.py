"""Real-DB concurrent-thread upsert test for research.dim_tag.

Spawns 8 threads upserting the same brand-new tag value. After:

* Exactly one row exists in research.dim_tag for that value.
* All 8 threads received the same canonical id.
* No thread surfaced an IntegrityError.

Uses a uuid-suffixed test tag so the row is guaranteed not to pre-exist
and cleanup is unambiguous. The test cleans up its own dim_tag row at
the end (DELETE — allowed CRUD per project rules; no DDL).

Skipped unless ``IMDR_MSSQL_HOST`` + ``IMDR_MSSQL_DATABASE`` are set,
since this test requires a real IMDR database connection.
"""
from __future__ import annotations

import sys
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text

_RESEARCH_ROOT = Path(__file__).resolve().parents[3] / "playground" / "research"
if str(_RESEARCH_ROOT) not in sys.path:
    sys.path.insert(0, str(_RESEARCH_ROOT))

from ingest.db import _upsert_tag_autocommit, ensure_model_id  # noqa: E402


def _live_engine():
    """Build a real engine via imdr settings (which loads .env)."""
    try:
        from imdr.config.settings import get_settings  # noqa: PLC0415
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"imdr settings unavailable: {exc}")
    s = get_settings()
    if s.mssql_database != "IMDR":
        pytest.skip(f"Refusing to run on non-IMDR database ({s.mssql_database!r})")
    if not s.mssql_host or s.mssql_host == "localhost":
        pytest.skip("IMDR_MSSQL_HOST not configured — real-DB integration test")
    url = (
        f"mssql+pyodbc://@{s.mssql_host}:{s.mssql_port}/{s.mssql_database}"
        f"?driver=ODBC+Driver+18+for+SQL+Server"
        f"&Trusted_Connection=yes"
        f"&Encrypt=yes"
        f"&TrustServerCertificate=yes"
        f"&LoginTimeout=30"
    )
    return create_engine(
        url, pool_size=12, max_overflow=4, pool_pre_ping=True,
        pool_timeout=30, echo=False, connect_args={"timeout": 30},
    )


def test_concurrent_upsert_same_tag_yields_one_row():
    engine = _live_engine()
    # Brand-new value guaranteed not to pre-exist; <= 50 chars (the
    # column cap) — 12-char uuid prefix fits comfortably.
    test_val = f"_test_race_{uuid.uuid4().hex[:12]}"
    n_threads = 8

    def _worker():
        return _upsert_tag_autocommit(
            engine, category="_test", value=test_val,
        )

    try:
        with ThreadPoolExecutor(max_workers=n_threads) as pool:
            futures = [pool.submit(_worker) for _ in range(n_threads)]
            ids = [f.result() for f in as_completed(futures)]

        # All threads must have returned an id (no None for non-empty input).
        assert all(i is not None for i in ids), f"some workers returned None: {ids}"
        # All threads must agree on the canonical id.
        assert len(set(ids)) == 1, (
            f"workers disagreed on canonical id: {sorted(set(ids))}"
        )

        # Exactly one row in the table for that value.
        with engine.connect() as conn:
            rows = conn.execute(
                text("SELECT id FROM research.dim_tag WHERE tag = :v"),
                {"v": test_val},
            ).all()
        assert len(rows) == 1, f"expected 1 row, got {len(rows)}: {rows}"
        assert rows[0][0] == ids[0]

    finally:
        # Cleanup — DELETE only (no DDL).
        with engine.begin() as conn:
            conn.execute(
                text("DELETE FROM research.dim_tag WHERE tag = :v"),
                {"v": test_val},
            )


def test_concurrent_ensure_model_id_yields_one_row():
    """Same race-safety check for research.dim_embedding_model."""
    engine = _live_engine()
    test_model = f"_test_model_{uuid.uuid4().hex[:12]}"
    n_threads = 8

    def _worker():
        return ensure_model_id(
            engine,
            provider="_test",
            model_name=test_model,
            dimensions=1024,
        )

    try:
        with ThreadPoolExecutor(max_workers=n_threads) as pool:
            futures = [pool.submit(_worker) for _ in range(n_threads)]
            ids = [f.result() for f in as_completed(futures)]

        assert len(set(ids)) == 1, (
            f"workers disagreed on canonical id: {sorted(set(ids))}"
        )

        with engine.connect() as conn:
            rows = conn.execute(
                text(
                    "SELECT id FROM research.dim_embedding_model "
                    "WHERE provider = :p AND model_name = :m AND dimensions = :d"
                ),
                {"p": "_test", "m": test_model, "d": 1024},
            ).all()
        assert len(rows) == 1
        assert rows[0][0] == ids[0]

    finally:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "DELETE FROM research.dim_embedding_model "
                    "WHERE provider = :p AND model_name = :m AND dimensions = :d"
                ),
                {"p": "_test", "m": test_model, "d": 1024},
            )
