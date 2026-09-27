"""Tests for scripts/econ/in/govt/ingest_filings.py — sidecar-title
preference over the hash-like filename-derived fallback.

Network- and DB-free (this module lazy-imports the heavy embed/Qdrant
stack only inside main(), so importing it here for the pure helpers is
cheap — matches the module's own docstring on that idiom).
"""

from __future__ import annotations

import importlib
import json
from pathlib import Path

# `scripts.econ.in.govt` can't be imported via a normal `from X.in.Y import`
# statement — `in` is a Python keyword. Same importlib workaround as the
# production callers, which invoke this module only via
# `python -m scripts.econ.in.govt.ingest_filings` (a dotted string).
ingest_filings = importlib.import_module("scripts.econ.in.govt.ingest_filings")
_load_sidecar = ingest_filings._load_sidecar
_sidecar_path = ingest_filings._sidecar_path
_title_from_filename = ingest_filings._title_from_filename


def test_title_from_filename_strips_hash_suffix_and_underscores():
    p = Path("PR6611_a1b2c3d4.pdf")
    assert _title_from_filename(p) == "PR6611"


def test_title_from_filename_hash_doc_code_stays_hash_like():
    """Documents the exact bug this feature fixes: an RBI doc-code
    filename with no sidecar produces a hash-like, non-human title."""
    p = Path("PR6611B8356F74E9A44FD9CF1A2BB7D83CE8E.pdf")
    assert _title_from_filename(p) == "PR6611B8356F74E9A44FD9CF1A2BB7D83CE8E"


def test_load_sidecar_returns_none_when_absent(tmp_path):
    pdf = tmp_path / "PR6611.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake")
    assert _load_sidecar(pdf) is None


def test_load_sidecar_reads_real_title(tmp_path):
    pdf = tmp_path / "PR6611.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake")
    sidecar = _sidecar_path(pdf)
    sidecar.write_text(
        json.dumps({
            "title": "Premature redemption under Sovereign Gold Bond (SGB) Scheme",
            "source_url": "https://rbidocs.rbi.org.in/rdocs/PressRelease/PDFs/PR6611.pdf",
            "publish_date": "2026-07-13",
        }),
        encoding="utf-8",
    )
    meta = _load_sidecar(pdf)
    assert meta is not None
    assert meta["title"] == "Premature redemption under Sovereign Gold Bond (SGB) Scheme"
    assert meta["publish_date"] == "2026-07-13"


def test_load_sidecar_returns_none_on_malformed_json(tmp_path):
    pdf = tmp_path / "PR6611.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake")
    _sidecar_path(pdf).write_text("{not valid json", encoding="utf-8")
    assert _load_sidecar(pdf) is None


def test_sidecar_preferred_over_filename_fallback(tmp_path):
    """The exact preference rule used in main()'s ingest loop:
    ``(sidecar or {}).get("title") or _title_from_filename(path)``."""
    pdf = tmp_path / "PR6611B8356F74E9A44FD9CF1A2BB7D83CE8E.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake")
    _sidecar_path(pdf).write_text(
        json.dumps({"title": "Real Headline From Listing Page"}), encoding="utf-8",
    )
    sidecar = _load_sidecar(pdf)
    title = (sidecar or {}).get("title") or _title_from_filename(pdf)
    assert title == "Real Headline From Listing Page"


def test_fallback_engages_when_sidecar_has_empty_title(tmp_path):
    pdf = tmp_path / "PR6611.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake")
    _sidecar_path(pdf).write_text(json.dumps({"title": ""}), encoding="utf-8")
    sidecar = _load_sidecar(pdf)
    title = (sidecar or {}).get("title") or _title_from_filename(pdf)
    assert title == "PR6611"
