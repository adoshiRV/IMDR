"""Unit tests for the dedup short-circuit branches of `ingest_email_one`.

The full email pipeline (chunk -> embed -> upload -> DB -> Qdrant) needs
live infra, but its two cheap GUARD branches are pure logic and must
return BEFORE any of that work:

1. `internet_message_id` already in `dim_report` -> skip (idempotency).
2. a portal-twin desk re-forward -> skip (precision-first merge gate).

Both are exercised here with a fake Engine (no SQL Server) and a
monkeypatched `find_portal_twin` (no real query). The coroutine is driven
with `asyncio.run` since the repo has no pytest-asyncio.
"""
from __future__ import annotations

import asyncio
import sys
from datetime import date
from pathlib import Path

_PR = Path(__file__).resolve().parents[3] / "playground" / "research"
if str(_PR) not in sys.path:
    sys.path.insert(0, str(_PR))

from ingest import email_pipeline as ep  # noqa: E402
from ingest.crawler_outlook import OutlookReportRef  # noqa: E402
from ingest.dedup_merge import PortalTwin  # noqa: E402


# ─── a minimal Engine stand-in ───────────────────────────────────────────
class _FakeResult:
    def __init__(self, row):
        self._row = row

    def first(self):
        return self._row


class _FakeConn:
    def __init__(self, row):
        self._row = row

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, *args, **kwargs):
        return _FakeResult(self._row)


class _FakeEngine:
    """connect() yields a conn whose single SELECT returns `row`."""

    def __init__(self, row):
        self._row = row

    def connect(self):
        return _FakeConn(self._row)


def _ref(imi="<msg@x>"):
    return OutlookReportRef(
        url="g", pdf_url="g", uuid=imi, title="[/] DB Fed Notes - June FOMC recap",
        publish_date=date(2026, 6, 18), vendor_code="db", folder="DB",
        archetype="desk_commentary", source="email",
        source_type="desk_commentary", internet_message_id=imi,
    )


def _run(engine, **overrides):
    kwargs = dict(
        ref=_ref(), classify_result=None, doc=None, body_text="",
        engine=engine, api_keys={}, do_embed=False, embed_model="",
    )
    kwargs.update(overrides)
    return asyncio.run(ep.ingest_email_one(**kwargs))


# ─── branch 1: internet_message_id already ingested ──────────────────────
def test_skip_when_message_id_exists(monkeypatch):
    # If the imi is already in dim_report we must NOT even consult the
    # portal-twin gate — prove it by making find_portal_twin explode.
    def _boom(*a, **k):
        raise AssertionError("portal-twin gate reached after imi short-circuit")

    monkeypatch.setattr(ep, "find_portal_twin", _boom)
    res = _run(_FakeEngine(row=(4242,)))
    assert res.report_id == 4242
    assert res.was_inserted is False
    assert res.dedup_reason == "internet_message_id"
    assert res.n_chunks == 0 and res.n_embeddings == 0


# ─── branch 2: portal-twin re-forward ────────────────────────────────────
def test_skip_when_portal_twin_found(monkeypatch):
    twin = PortalTwin(report_id=99, portal_title="Fed Notes: June FOMC recap", score=0.92)
    monkeypatch.setattr(ep, "find_portal_twin", lambda *a, **k: twin)
    res = _run(_FakeEngine(row=None))            # imi NOT yet ingested
    assert res.report_id == 99
    assert res.was_inserted is False
    assert res.dedup_reason == "portal_twin(0.92)"


def test_portal_twin_gate_queried_with_ref_identity(monkeypatch):
    # On the imi-not-yet-seen path the gate must be consulted with THIS
    # ref's vendor/date/title (the inputs find_portal_twin matches on).
    seen = {}

    def _twin(engine, *, vendor_code, publish_date, title):
        seen.update(vendor_code=vendor_code, publish_date=publish_date, title=title)
        return PortalTwin(report_id=1, portal_title="Fed Notes: June FOMC recap", score=0.81)

    monkeypatch.setattr(ep, "find_portal_twin", _twin)
    _run(_FakeEngine(row=None))
    assert seen["vendor_code"] == "db"
    assert seen["publish_date"] == date(2026, 6, 18)
    assert seen["title"] == "[/] DB Fed Notes - June FOMC recap"
