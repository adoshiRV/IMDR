"""Unit tests for the US govt filings discovery-probe parse layers.

No network. Exercises the pure parse functions of the two representative
probe shapes: the Fed speeches JSON firehose (Shape A) and the SLOOS
slug-keyed HTML listing (Shape B).
"""

from __future__ import annotations

import datetime

from scripts.econ.us.govt import probe_fed_speeches as speeches
from scripts.econ.us.govt import probe_sloos as sloos


class TestFedSpeechesParse:
    def _feed(self, *recs: dict) -> str:
        import json
        return json.dumps(list(recs))

    def test_valid_record_parsed(self) -> None:
        payload = self._feed(
            {"d": "6/6/2026 12:00:00 PM", "t": "A speech",
             "s": "Governor X", "lo": "DC", "l": "/newsevents/speech/x20260606a.htm"}
        )
        items = speeches._parse_feed(payload, limit=40)
        assert len(items) == 1
        it = items[0]
        assert it.vendor_code == "fed"
        assert it.publish_date == datetime.date(2026, 6, 6)
        assert it.source_url.endswith("/newsevents/speech/x20260606a.htm")
        assert it.doc_type == "speech"

    def test_testimony_link_maps_to_testimony_doctype(self) -> None:
        payload = self._feed(
            {"d": "1/2/2026", "t": "Testimony before Congress",
             "l": "/newsevents/testimony/x20260102a.htm"}
        )
        items = speeches._parse_feed(payload, limit=40)
        assert items[0].doc_type == "testimony"

    def test_records_missing_required_fields_skipped(self) -> None:
        payload = self._feed(
            {"d": "6/6/2026", "t": "", "l": "/x.htm"},          # no title
            {"d": "bad-date", "t": "T", "l": "/y.htm"},          # bad date
            {"d": "6/6/2026", "t": "Good", "l": ""},             # no link
        )
        assert speeches._parse_feed(payload, limit=40) == []

    def test_limit_truncates_newest_first(self) -> None:
        payload = self._feed(
            {"d": "1/1/2024", "t": "old", "l": "/a.htm"},
            {"d": "1/1/2026", "t": "new", "l": "/b.htm"},
            {"d": "1/1/2025", "t": "mid", "l": "/c.htm"},
        )
        items = speeches._parse_feed(payload, limit=2)
        assert [it.title for it in items] == ["new", "mid"]

    def test_bom_prefixed_json_tolerated(self) -> None:
        payload = "﻿" + self._feed(
            {"d": "6/6/2026", "t": "T", "l": "/x.htm"}
        )
        assert len(speeches._parse_feed(payload, limit=40)) == 1


class TestSloosParse:
    def test_slug_keyed_listing_parsed(self) -> None:
        html = (
            '<a href="/data/sloos/sloos-202604.htm">Apr 2026</a>'
            '<a href="/data/sloos/sloos-202601.htm">Jan 2026</a>'
        )
        items = sloos._parse_listing(html, limit=16)
        assert len(items) == 2
        newest = items[0]
        assert newest.publish_date == datetime.date(2026, 4, 1)
        assert newest.pdf_url.endswith("/data/documents/sloos-202604.pdf")
        assert newest.doc_type == "survey"

    def test_duplicate_slugs_deduped(self) -> None:
        html = (
            '<a href="/data/sloos/sloos-202604.htm">x</a>'
            '<a href="/data/sloos/sloos-202604.htm">x again</a>'
        )
        assert len(sloos._parse_listing(html, limit=16)) == 1

    def test_limit_applied(self) -> None:
        html = "".join(
            f'<a href="/data/sloos/sloos-2026{m:02d}.htm">m</a>' for m in (1, 4, 7, 10)
        )
        assert len(sloos._parse_listing(html, limit=2)) == 2

    def test_date_from_yyyymm_bad_value_is_none(self) -> None:
        assert sloos._date_from_yyyymm("2026zz") is None
        assert sloos._date_from_yyyymm("202604") == datetime.date(2026, 4, 1)
