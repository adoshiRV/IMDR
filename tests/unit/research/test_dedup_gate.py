"""Tests for the two-layer dedup gate in ingest/pipeline.py + ingest/db.py.

Layer 1 (pipeline.py): pre-fetch check on (vendor_code, pdf_path) — fires
  before any network call; the primary guard against watermarked-vendor re-ingests.

Layer 2 (db.py): fallback check inside write_report on
  (vendor_id, publish_date::date, LOWER(title)) — catches case-variant title
  duplicates (e.g. Barclays changing capitalisation between runs).

None of these tests open a real DB connection.
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, call

import pytest

_RESEARCH_ROOT = Path(__file__).resolve().parents[3] / "playground" / "research"
if str(_RESEARCH_ROOT) not in sys.path:
    sys.path.insert(0, str(_RESEARCH_ROOT))

from ingest.db import (  # noqa: E402
    _get_existing_by_date_title,
    write_report,
)
from ingest.models import Document, ReportMeta  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_doc(content_hash: bytes = b"\x00" * 32) -> Document:
    return Document(
        pdf_bytes=b"%PDF-fake",
        content_hash=content_hash,
        full_text="body text",
        page_count=1,
        parser_version="pymupdf-test",
        pages_text=("body text",),
    )


def _make_meta(title: str = "Report Title", pub_date: date | None = None) -> ReportMeta:
    return ReportMeta(
        vendor_code="db",
        vendor_id=18,
        title=title,
        publish_date=pub_date or date(2026, 6, 2),
        pdf_url="https://example.com/report.pdf",
        sharepoint_path=None,
    )


def _conn_returning(*seq):
    """Build a mock Connection whose .execute(...).first() returns items from seq."""
    conn = MagicMock(name="Connection")
    conn.execute.return_value.first.side_effect = list(seq)
    return conn


# ---------------------------------------------------------------------------
# Layer 2: _get_existing_by_date_title
# ---------------------------------------------------------------------------

class TestGetExistingByDateTitle:
    def test_returns_id_when_match(self):
        conn = _conn_returning((42,))
        result = _get_existing_by_date_title(conn, 18, date(2026, 6, 2), "My Report")
        assert result == 42

    def test_returns_none_when_no_match(self):
        conn = _conn_returning(None)
        result = _get_existing_by_date_title(conn, 18, date(2026, 6, 2), "My Report")
        assert result is None

    def test_passes_lowered_title_and_vendor_id(self):
        """Verify the SQL parameters passed — caller controls normalisation."""
        conn = _conn_returning(None)
        _get_existing_by_date_title(conn, 18, date(2026, 6, 2), "Tracking Shelf Space")
        executed_params = conn.execute.call_args[0][1]
        assert executed_params["vid"] == 18
        assert executed_params["t"] == "Tracking Shelf Space"  # raw — SQL does LOWER()


# ---------------------------------------------------------------------------
# Layer 2: write_report dedup paths
# ---------------------------------------------------------------------------

class TestWriteReportDedup:
    """write_report should return was_inserted=False on both fallback checks."""

    def _make_conn_hash_hit(self, report_id: int):
        """Simulates content_hash match on first execute."""
        return _conn_returning((report_id,))

    def _make_conn_hash_miss_title_hit(self, vendor_id_row, report_id: int):
        """content_hash miss → vendor lookup → date+title hit."""
        conn = MagicMock(name="Connection")
        conn.execute.return_value.first.side_effect = [
            None,           # _get_existing_report_id: no hash match
            (vendor_id_row,),  # _resolve_vendor_id
            (report_id,),   # _get_existing_by_date_title
        ]
        return conn

    def test_content_hash_dedup_returns_false(self):
        conn = self._make_conn_hash_hit(99)
        doc = _make_doc(b"\xab" * 32)
        meta = _make_meta()
        rid, inserted, chunk_ids, mid = write_report(
            conn=conn, meta=meta, doc=doc,
            chunks=[], embeddings=[],
        )
        assert rid == 99
        assert inserted is False
        assert chunk_ids == {}
        assert mid is None

    def test_date_title_dedup_returns_false(self):
        """Same date+title (different hash, different path) → was_inserted=False."""
        conn = self._make_conn_hash_miss_title_hit(18, 77)
        doc = _make_doc(b"\xcd" * 32)
        meta = _make_meta(title="Early Morning Reid: Macro Strategy")
        rid, inserted, chunk_ids, mid = write_report(
            conn=conn, meta=meta, doc=doc,
            chunks=[], embeddings=[],
        )
        assert rid == 77
        assert inserted is False

    def test_different_date_same_title_not_deduped(self):
        """Same title, different date → should proceed to insert (different edition)."""
        conn = MagicMock(name="Connection")
        conn.execute.return_value.first.side_effect = [
            None,   # content_hash miss
            (18,),  # vendor_id lookup
            None,   # date+title miss (different date → different edition)
            (999,), # INSERT OUTPUT INSERTED.id
        ]
        doc = _make_doc(b"\x01" * 32)
        meta_a = _make_meta(title="Early Morning Reid: Macro Strategy", pub_date=date(2026, 6, 2))
        rid, inserted, _, _ = write_report(
            conn=conn, meta=meta_a, doc=doc,
            chunks=[], embeddings=[],
        )
        assert inserted is True
        assert rid == 999

    def test_same_date_different_title_not_deduped(self):
        """Same date, different title → should proceed to insert."""
        conn = MagicMock(name="Connection")
        conn.execute.return_value.first.side_effect = [
            None,   # content_hash miss
            (18,),  # vendor_id lookup
            None,   # date+title miss
            (888,), # INSERT OUTPUT INSERTED.id
        ]
        doc = _make_doc(b"\x02" * 32)
        meta = _make_meta(title="A Completely Different Report", pub_date=date(2026, 6, 2))
        rid, inserted, _, _ = write_report(
            conn=conn, meta=meta, doc=doc,
            chunks=[], embeddings=[],
        )
        assert inserted is True
        assert rid == 888


# ---------------------------------------------------------------------------
# Layer 1: pipeline.py pre-fetch dedup on (vendor_code, pdf_path)
# ---------------------------------------------------------------------------

class TestPipelinePreFetchDedup:
    """ingest_one must short-circuit before fetch when pdf_path already exists."""

    def test_returns_not_inserted_when_path_already_exists(self, tmp_path):
        """Pre-fetch dedup fires: no fetch, no parse, was_inserted=False."""
        import asyncio  # noqa: PLC0415
        from ingest.models import ReportMeta  # noqa: PLC0415
        from ingest.pipeline import ingest_one  # noqa: PLC0415

        meta = ReportMeta(
            vendor_code="db",
            vendor_id=18,
            title="Early Morning Reid: Macro Strategy",
            publish_date=date(2026, 6, 2),
            pdf_url="https://example.com/report.pdf",
            sharepoint_path=None,
        )
        sp_path = "2026/06/02/db/Early_Morning_Reid_Macro_Strategy_01KT39PE.pdf"

        engine = MagicMock(name="Engine")
        conn_ctx = MagicMock()
        conn_ctx.__enter__ = MagicMock(return_value=conn_ctx)
        conn_ctx.__exit__ = MagicMock(return_value=False)
        conn_ctx.execute.return_value.first.return_value = (2591, sp_path)
        engine.connect.return_value = conn_ctx

        fetch_called = []

        async def _mock_fetch(url, profile_dir):
            fetch_called.append(url)
            return b"%PDF-fake"

        async def _run():
            with patch("ingest.pipeline.fetch_pdf", side_effect=_mock_fetch):
                return await ingest_one(
                    url=meta.pdf_url,
                    meta=meta,
                    sharepoint_relative_path=sp_path,
                    profile_dir=tmp_path,
                    api_keys={},
                    engine=engine,
                )

        result = asyncio.run(_run())

        assert result.was_inserted is False
        assert result.report_id == 2591
        assert result.sharepoint_path == sp_path
        assert fetch_called == [], "fetch must NOT be called when path already exists"

    def test_proceeds_to_fetch_when_path_is_new(self, tmp_path):
        """Pre-fetch dedup passes: fetch is called for a genuinely new path."""
        import asyncio  # noqa: PLC0415
        from ingest.models import ReportMeta  # noqa: PLC0415
        from ingest.pipeline import ingest_one  # noqa: PLC0415

        meta = ReportMeta(
            vendor_code="goldman",
            vendor_id=9,
            title="Global Markets Daily",
            publish_date=date(2026, 6, 15),
            pdf_url="https://example.com/new.pdf",
            sharepoint_path=None,
        )
        sp_path = "2026/06/15/goldman/Global_Markets_Daily_abcd1234.pdf"

        engine = MagicMock(name="Engine")
        fetch_called = []

        call_count = {"n": 0}

        def _mock_connect():
            call_count["n"] += 1
            ctx = MagicMock()
            ctx.__enter__ = MagicMock(return_value=ctx)
            ctx.__exit__ = MagicMock(return_value=False)
            if call_count["n"] == 1:
                ctx.execute.return_value.first.return_value = None  # path miss
            elif call_count["n"] == 2:
                ctx.execute.return_value.first.return_value = None  # hash miss
            return ctx

        engine.connect.side_effect = _mock_connect

        async def _mock_fetch(url, profile_dir):
            fetch_called.append(url)
            return b"%PDF-fake"

        async def _run():
            with patch("ingest.pipeline.fetch_pdf", side_effect=_mock_fetch):
                with patch("ingest.pipeline.parse_pdf") as mock_parse:
                    mock_parse.return_value = MagicMock(
                        content_hash=b"\x00" * 32,
                        page_count=1,
                        pdf_bytes=b"%PDF-fake",
                        full_text="",
                    )
                    with patch("ingest.pipeline.chunk_doc", return_value=[]):
                        with patch("ingest.pipeline.upload_pdf", new_callable=AsyncMock, return_value=sp_path):
                            with patch("ingest.pipeline.embed_mod.embed_chunks", new_callable=AsyncMock, return_value=[]):
                                # resolve_tag_ids and write_report are imported
                                # inside ingest_one via local import from .db;
                                # patch them at their source module.
                                with patch("ingest.db.resolve_tag_ids", return_value=()):
                                    with patch("ingest.db.write_report", return_value=(1234, True, {}, None)):
                                        return await ingest_one(
                                            url=meta.pdf_url,
                                            meta=meta,
                                            sharepoint_relative_path=sp_path,
                                            profile_dir=tmp_path,
                                            api_keys={},
                                            engine=engine,
                                            embed=False,
                                        )

        asyncio.run(_run())
        assert fetch_called == [meta.pdf_url], "fetch must be called for a new path"
