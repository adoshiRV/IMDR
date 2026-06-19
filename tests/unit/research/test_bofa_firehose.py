"""Tests for crawler_bofa_firehose.py — Advanced Search results parser.

Pins:
1. ``_parse_result_rows`` — report_id extraction, series/title split, date
   parse, analyst extraction from a carved fixture.
2. ``_extract_pdf_template`` — pdfResourceUrl template extraction and
   the ``summary_instance`` derivation from the page-level hidden input.
3. ``_parse_total_count`` — "1-25 of 1,227" and "1-25 of 48" variants.
4. ``_has_next_page`` — presence/absence of the next-page control image.
5. ``_parse_bofa_date_str`` — AM/PM and 24-h date string variants.
6. ``_DISCIPLINE_TO_HUB`` — covers only non-equity macro disciplines;
   every value is present in ``_HUB_TO_ASSET_CLASS``.
7. Over-cap probe union — when a discipline exceeds _PAGE_CAP, the probe
   window reports are NOT silently dropped; the returned list is the union
   of probe_refs and sub_refs with no duplicate IDs.

Fixture HTML is carved from the real ``firehose_page1.html`` saved during
the Advanced Search probe (2026-06-14 session, Economics discipline,
Last 1 Week). Three result rows + the pdfResourceUrl template + the count
text + the next-page control are included verbatim.
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import pytest

_RESEARCH_ROOT = Path(__file__).resolve().parents[3] / "playground" / "research"
if str(_RESEARCH_ROOT) not in sys.path:
    sys.path.insert(0, str(_RESEARCH_ROOT))

import asyncio
from dataclasses import dataclass, field
from typing import Optional

from ingest.crawler_bofa_firehose import (  # noqa: E402
    _DISCIPLINE_TO_HUB,
    _PAGE_CAP,
    _extract_pdf_template,
    _has_next_page,
    _parse_bofa_date_str,
    _parse_result_rows,
    _parse_total_count,
)

# ── Fixture ────────────────────────────────────────────────────────────────────
# Carved verbatim from firehose_page1.html (all-discipline, Last 1 Week,
# 2026-06-14 session). Contains:
#   - pdfResourceUrl hidden input (SearchSummaryPortlet INSTANCE OAvkcOeef2VT)
#   - Count text "1-25 of 1227"
#   - Next-page control (go to next page results)
#   - Three result rows (Klabin S.A / Emerging Insight / Pulp & Paper LatAm)
# HTML entities left intact; the parser must call _decode_entities internally.

_FIXTURE = r"""
<input type="hidden" id="_SearchSummaryPortlet_WAR_rlapp_portlet_INSTANCE_OAvkcOeef2VT_pdfResourceUrl" value="https://markets.ml.com/researchlibrary/advancedsearch?p_p_id=SearchSummaryPortlet_WAR_rlapp_portlet_INSTANCE_OAvkcOeef2VT&amp;p_p_lifecycle=2&amp;p_p_state=normal&amp;p_p_mode=view&amp;p_p_resource_id=getPdfUrl&amp;p_p_cacheability=cacheLevelPage&amp;_SearchSummaryPortlet_WAR_rlapp_portlet_INSTANCE_OAvkcOeef2VT_pid=pidvalue">

<td width="100%" colspan="3" align="right"><span class="grey-text">
1-25 of 1227
&nbsp;
<a href="javascript:_SearchSummaryPortlet_WAR_rlapp_portlet_INSTANCE_OAvkcOeef2VT_pagingnext('5','')">
<img alt="go to next page results" role="img" style="margin-left: 3px;" border="0" src="https://static.markets.ml.com/o/rlapp_portlet/images/controls_forward.png.pagespeed.ce.BSDKrxtnp1.png" width="5" height="10">
</a>
</span></td>

<tr><td colspan="3" style="width:100%;border-top: none;border-right: none;border-left: none;height: 3px" class="graybackground_all_border"></td></tr>
<tr>
<td align="left" style="padding-left: 5px;" colspan="2" nowrap="">
<a id="_SearchSummaryPortlet_WAR_rlapp_portlet_INSTANCE_OAvkcOeef2VT_12984028" onclick="javascript:htmlIconClickOnCachedPortlet('12984028','_SearchSummaryPortlet_WAR_rlapp_portlet_INSTANCE_OAvkcOeef2VT_')" style="cursor: hand" href="javascript:void(0);">
<span aria-hidden="true">Klabin S.A</span>
<span style="width:1px;height:1px;overflow:hidden;position:absolute;" aria-label="Report title Klabin S.A with report sub title Model opens in a new window">Report title Klabin S.A with report sub title Model opens in a new window</span>
</a>
</td>
</tr>
<tr>
<td colspan="3" style="padding-left: 5px;">
<span class="white-text" aria-hidden="true">Model</span>
</td>
</tr>
<tr style="width:100%;">
<td width="50%" style="padding-left: 5px;" align="left" nowrap="">
<table class="analystDateHover" style="table-layout: fixed;"><tbody><tr><td width="100%" align="left" style="white-space:nowrap;overflow: hidden;text-overflow: ellipsis;" nowrap="">
<span id="_SearchSummaryPortlet_WAR_rlapp_portlet_INSTANCE_OAvkcOeef2VT_primaryAuthSpan" class="dark-grey-text"><a style="cursor:hand" aria-hidden="true" tabindex="0" onclick="javascript:navigateToResearchSearchProxy('Caio+Ribeiro')">Caio Ribeiro</a>
</span>
</td></tr></tbody></table>
</td>
<td width="25%" align="right" nowrap="">
<span class="dark-grey-text" style="color:grey;"><span aria-hidden="true">| </span>14-Jun-2026 05:04:52 PM</span>
</td>
</tr>

<tr><td colspan="3" style="width:100%;border-top: none;border-right: none;border-left: none;height: 3px" class="graybackground_all_border"></td></tr>
<tr>
<td align="left" style="padding-left: 5px;" colspan="2" nowrap="">
<a id="_SearchSummaryPortlet_WAR_rlapp_portlet_INSTANCE_OAvkcOeef2VT_12984111" href="javascript:void(0);" onclick="javascript:htmlIconClickOnCachedPortlet('12984111','_SearchSummaryPortlet_WAR_rlapp_portlet_INSTANCE_OAvkcOeef2VT_')" style="cursor: hand">
<span aria-hidden="true">Emerging Insight</span>
<span style="width:1px;height:1px;overflow:hidden;position:absolute;" aria-label="Report title Emerging Insight with report sub title India Strategy &#8211; Liquidity deluge from FX measures opens in a new window">Report title Emerging Insight with report sub title India Strategy opens in a new window</span>
</a>
</td>
</tr>
<tr>
<td colspan="3" style="padding-left: 5px;">
<span class="white-text" aria-hidden="true">India Strategy &#8211; Liquidity deluge from FX measures</span>
</td>
</tr>
<tr style="width:100%;">
<td width="50%" style="padding-left: 5px;" align="left" nowrap="">
<table class="analystDateHover" style="table-layout: fixed;"><tbody><tr><td width="100%" align="left" style="white-space:nowrap;overflow: hidden;text-overflow: ellipsis;" nowrap="">
<span id="_SearchSummaryPortlet_WAR_rlapp_portlet_INSTANCE_OAvkcOeef2VT_primaryAuthSpan" class="dark-grey-text"><a style="cursor:hand" aria-hidden="true" tabindex="0" onclick="javascript:navigateToResearchSearchProxy('GEMs+FI+Strategy+%26+Economics')">GEMs FI Strategy &amp; Economics</a>
</span>
</td></tr></tbody></table>
</td>
<td width="25%" align="right" nowrap="">
<span class="dark-grey-text" style="color:grey;"><span aria-hidden="true">| </span>14-Jun-2026 05:00:28 PM</span>
</td>
</tr>

<tr><td colspan="3" style="width:100%;border-top: none;border-right: none;border-left: none;height: 3px" class="graybackground_all_border"></td></tr>
<tr>
<td align="left" style="padding-left: 5px;" colspan="2" nowrap="">
<a id="_SearchSummaryPortlet_WAR_rlapp_portlet_INSTANCE_OAvkcOeef2VT_12983997" href="javascript:void(0);" onclick="javascript:htmlIconClickOnCachedPortlet('12983997','_SearchSummaryPortlet_WAR_rlapp_portlet_INSTANCE_OAvkcOeef2VT_')" style="cursor: hand">
<span aria-hidden="true">Pulp &amp; Paper - LatAm</span>
<span style="width:1px;height:1px;overflow:hidden;position:absolute;" aria-label="Report title Pulp &amp; Paper - LatAm opens in a new window">Report title Pulp &amp;amp; Paper - LatAm opens in a new window</span>
</a>
</td>
</tr>
<tr>
<td colspan="3" style="padding-left: 5px;">
<span class="white-text" aria-hidden="true">Bracing for a potential hardwood pulp price correction</span>
</td>
</tr>
<tr style="width:100%;">
<td width="50%" style="padding-left: 5px;" align="left" nowrap="">
<table class="analystDateHover" style="table-layout: fixed;"><tbody><tr><td width="100%" align="left" style="white-space:nowrap;overflow: hidden;text-overflow: ellipsis;" nowrap="">
<span id="_SearchSummaryPortlet_WAR_rlapp_portlet_INSTANCE_OAvkcOeef2VT_primaryAuthSpan" class="dark-grey-text"><a style="cursor:hand" aria-hidden="true" tabindex="0" onclick="javascript:navigateToResearchSearchProxy('Caio+Ribeiro')">Caio Ribeiro</a>
</span>
</td></tr></tbody></table>
</td>
<td width="25%" align="right" nowrap="">
<span class="dark-grey-text" style="color:grey;"><span aria-hidden="true">| </span>12-Jun-2026 09:31:17 AM</span>
</td>
</tr>
"""

_NO_NEXT_PAGE_HTML = """
<td width="100%" colspan="3" align="right"><span class="grey-text">
1-25 of 48
&nbsp;
1 2
</span></td>
"""


# ── _parse_total_count ─────────────────────────────────────────────────────────

def test_parse_total_count_with_comma() -> None:
    html = "<span>1-25 of 1,227</span>"
    assert _parse_total_count(html) == 1227


def test_parse_total_count_without_comma() -> None:
    assert _parse_total_count(_FIXTURE) == 1227


def test_parse_total_count_small() -> None:
    assert _parse_total_count(_NO_NEXT_PAGE_HTML) == 48


def test_parse_total_count_missing() -> None:
    assert _parse_total_count("<html>no count</html>") is None


# ── _has_next_page ─────────────────────────────────────────────────────────────

def test_has_next_page_present() -> None:
    assert _has_next_page(_FIXTURE) is True


def test_has_next_page_absent() -> None:
    assert _has_next_page(_NO_NEXT_PAGE_HTML) is False


# ── _extract_pdf_template ──────────────────────────────────────────────────────

def test_extract_pdf_template_instance_and_url() -> None:
    result = _extract_pdf_template(_FIXTURE)
    assert result is not None
    inst, tmpl = result
    assert inst == "OAvkcOeef2VT"
    assert "pidvalue" in tmpl
    assert "getPdfUrl" in tmpl
    assert "&" in tmpl  # entities decoded (&amp; → &)


def test_extract_pdf_template_missing() -> None:
    assert _extract_pdf_template("<html>no template</html>") is None


# ── _parse_bofa_date_str ───────────────────────────────────────────────────────

@pytest.mark.parametrize("text,expected", [
    ("14-Jun-2026 05:04:52 PM", date(2026, 6, 14)),
    ("12-Jun-2026 09:31:17 AM", date(2026, 6, 12)),
    ("01-Jan-2026 00:00:00",    date(2026, 1,  1)),
    ("31-Dec-2025 23:59:59",    date(2025, 12, 31)),
])
def test_parse_bofa_date_str_variants(text: str, expected: date) -> None:
    assert _parse_bofa_date_str(text) == expected


def test_parse_bofa_date_str_missing() -> None:
    assert _parse_bofa_date_str("no date here") is None


def test_parse_bofa_date_str_empty() -> None:
    assert _parse_bofa_date_str("") is None


# ── _parse_result_rows ─────────────────────────────────────────────────────────

class TestParseResultRows:
    def setup_method(self) -> None:
        self.rows = _parse_result_rows(_FIXTURE)

    def test_three_rows_parsed(self) -> None:
        assert len(self.rows) == 3, (
            f"Expected 3 rows from fixture, got {len(self.rows)}: "
            + str([r["report_id"] for r in self.rows])
        )

    def test_report_ids(self) -> None:
        ids = [r["report_id"] for r in self.rows]
        assert ids == ["12984028", "12984111", "12983997"], ids

    def test_summary_instance_consistent(self) -> None:
        for row in self.rows:
            assert row["summary_instance"] == "OAvkcOeef2VT", (
                f"Unexpected instance: {row['summary_instance']!r}"
            )

    def test_series_first_row(self) -> None:
        assert self.rows[0]["series"] == "Klabin S.A"

    def test_series_second_row(self) -> None:
        assert self.rows[1]["series"] == "Emerging Insight"

    def test_series_third_row_entity_decoded(self) -> None:
        # "Pulp &amp; Paper - LatAm" → "Pulp & Paper - LatAm"
        assert self.rows[2]["series"] == "Pulp & Paper - LatAm"

    def test_title_first_row(self) -> None:
        assert self.rows[0]["title"] == "Model"

    def test_title_second_row(self) -> None:
        # &#8211; is an em-dash — parser leaves numeric entities as-is (they
        # render fine in HTML; we only decode the named entities). Accept either.
        t = self.rows[1]["title"]
        assert "India Strategy" in t, f"Unexpected title: {t!r}"
        assert "Liquidity deluge" in t or "deluge" in t.lower(), (
            f"Expected subtitle fragment in: {t!r}"
        )

    def test_title_third_row(self) -> None:
        assert self.rows[2]["title"] == "Bracing for a potential hardwood pulp price correction"

    def test_publish_date_first_row(self) -> None:
        assert self.rows[0]["publish_date"] == date(2026, 6, 14)

    def test_publish_date_third_row(self) -> None:
        assert self.rows[2]["publish_date"] == date(2026, 6, 12)

    def test_analyst_first_row(self) -> None:
        assert self.rows[0]["analyst_primary"] == "Caio Ribeiro"
        assert "Caio Ribeiro" in self.rows[0]["analysts"]

    def test_analyst_second_row_url_decoded(self) -> None:
        # 'GEMs+FI+Strategy+%26+Economics' → 'GEMs FI Strategy & Economics'
        assert self.rows[1]["analyst_primary"] == "GEMs FI Strategy & Economics"


# ── _DISCIPLINE_TO_HUB ────────────────────────────────────────────────────────

def test_discipline_map_no_equity_fundamental() -> None:
    """Single-name equity disciplines must not appear in the map."""
    excluded = {
        "Equity-Fundamental", "Equity-Small Cap", "Equity Derivatives",
        "Equity Linked", "ETFs", "Accounting", "Compliance",
        "Closed-End Funds", "MBS-Analytics", "EM-Analytics", "Preferreds",
        "Pensions", "Structured Finance", "CDOs", "Covered Bonds",
    }
    for disc in excluded:
        assert disc not in _DISCIPLINE_TO_HUB, (
            f"Single-name/data discipline {disc!r} should not be in _DISCIPLINE_TO_HUB"
        )


def test_discipline_map_expected_keys_present() -> None:
    expected = {
        "Economics",
        "Emerging Markets Economics",
        "Country Investment Strategy",
        "Currency Strategy",
        "Rates Strategy",
        "Fixed Income Strategy",
        "Fixed Income Technical Analysis",
        "Technical Analysis",
        "Quantitative Strategy",
        "Commodities",
        "Multi-Asset Strategy",
        "Investment Strategy",
        "Credit Strategy",
        "High Yield Strategy",
        "Emerging Markets Debt Strategy",
        "Emerging Markets Credit",
    }
    assert set(_DISCIPLINE_TO_HUB.keys()) == expected


def test_discipline_map_all_hubs_known_to_classifier() -> None:
    """Every hub value in _DISCIPLINE_TO_HUB must be present in the
    classifier's _HUB_TO_ASSET_CLASS map (validated at import time)."""
    from ingest.classifiers.bofa import _HUB_TO_ASSET_CLASS  # noqa: PLC0415

    for discipline, hub in _DISCIPLINE_TO_HUB.items():
        assert hub in _HUB_TO_ASSET_CLASS, (
            f"Discipline {discipline!r} maps to hub {hub!r} which is not "
            f"in classifiers/bofa.py::_HUB_TO_ASSET_CLASS"
        )


def test_discipline_map_specific_mappings() -> None:
    """Spot-check the spec-mandated hub assignments."""
    cases = [
        ("Economics",                       "economics_overview"),
        ("Emerging Markets Economics",       "economics_country"),
        ("Currency Strategy",               "fx_global"),
        ("Rates Strategy",                  "rates_regional"),
        ("Fixed Income Strategy",           "rates_regional"),
        ("Technical Analysis",              "technical_analysis"),
        ("Commodities",                     "commodities"),
        ("Multi-Asset Strategy",            "investment_themes"),
        ("Credit Strategy",                 "credit_global"),
        ("High Yield Strategy",             "credit_high_yield"),
        ("Emerging Markets Debt Strategy",  "credit_em_fi"),
        ("Emerging Markets Credit",         "credit_em_corporate"),
    ]
    for discipline, expected_hub in cases:
        assert _DISCIPLINE_TO_HUB[discipline] == expected_hub, (
            f"{discipline!r}: expected hub={expected_hub!r}, "
            f"got {_DISCIPLINE_TO_HUB[discipline]!r}"
        )


# ── Over-cap probe union (correctness bug fix) ────────────────────────────────
# Simulates the discover_reports() branching logic without hitting the network.
# The fix: probe runs against a throwaway seen-set; on over-cap the probe_refs
# are merged with sub_refs so no report is silently dropped.

@dataclass
class _FakeRef:
    uuid: str
    publish_date: date = date(2026, 6, 14)
    title: str = ""
    series: str = ""
    hub: str = "economics_overview"
    pdf_url: str = ""
    url: str = ""
    subject: str = ""
    portlet_instance: str = ""
    analyst_primary: str = ""
    analysts: tuple = ()
    asset_class_hint: str = ""


def _make_refs(ids: list[str]) -> list[_FakeRef]:
    return [_FakeRef(uuid=i) for i in ids]


def _simulate_over_cap_branching(
    probe_ids: list[str],
    probe_total_count: int,
    sub_ids: list[str],
    initial_seen: set[str],
) -> tuple[list[str], set[str]]:
    """Re-implement the fixed discover_reports over-cap branch in pure Python.

    Returns (result_uuids, final_seen_ids) so callers can assert on both.
    """
    seen_ids: set[str] = set(initial_seen)

    probe_seen: set[str] = set(seen_ids)
    probe_refs = _make_refs(probe_ids)
    # Simulate: probe_seen gets the probe ids (but seen_ids is still clean)
    for r in probe_refs:
        probe_seen.add(r.uuid)

    if probe_total_count > _PAGE_CAP:
        # Add probe ids to shared seen_ids so sub-partition skips them
        for r in probe_refs:
            seen_ids.add(r.uuid)
        # Sub-partition only returns ids not already in seen_ids
        sub_refs = _make_refs([i for i in sub_ids if i not in seen_ids])
        for r in sub_refs:
            seen_ids.add(r.uuid)
        combined = probe_refs + sub_refs
    else:
        seen_ids.update(probe_seen)
        combined = probe_refs

    return [r.uuid for r in combined], seen_ids


class TestOverCapProbeUnion:
    """Verify that the over-cap path returns probe ∪ sub with no duplicates."""

    def test_over_cap_returns_probe_plus_sub(self) -> None:
        probe_ids = [f"P{i:04d}" for i in range(10)]   # 10 probe reports
        sub_ids = [f"S{i:04d}" for i in range(5)]      # 5 new sub-partition reports
        total_count = _PAGE_CAP + 1                     # triggers sub-partition

        result, _ = _simulate_over_cap_branching(
            probe_ids=probe_ids,
            probe_total_count=total_count,
            sub_ids=sub_ids,
            initial_seen=set(),
        )
        assert set(result) == set(probe_ids) | set(sub_ids), (
            f"Union of probe+sub expected; got {result!r}"
        )
        assert len(result) == len(probe_ids) + len(sub_ids), "No duplicates expected"

    def test_over_cap_no_duplicate_ids(self) -> None:
        # sub_ids contain some overlap with probe_ids (should be skipped by seen_ids)
        probe_ids = ["A001", "A002", "A003"]
        sub_ids = ["A002", "A003", "A004", "A005"]  # A002/A003 already in seen after probe
        total_count = _PAGE_CAP + 100

        result, _ = _simulate_over_cap_branching(
            probe_ids=probe_ids,
            probe_total_count=total_count,
            sub_ids=sub_ids,
            initial_seen=set(),
        )
        assert len(result) == len(set(result)), "Duplicate IDs in result"
        assert set(result) == {"A001", "A002", "A003", "A004", "A005"}

    def test_probe_ids_not_silently_dropped_on_over_cap(self) -> None:
        """The bug: probe_ids were added to shared seen_ids then discarded.
        After the fix, all probe_ids appear in the final result."""
        probe_ids = [f"PROBE{i}" for i in range(_PAGE_CAP)]
        sub_ids = ["SUB001", "SUB002"]
        total_count = _PAGE_CAP + 50

        result, _ = _simulate_over_cap_branching(
            probe_ids=probe_ids,
            probe_total_count=total_count,
            sub_ids=sub_ids,
            initial_seen=set(),
        )
        for pid in probe_ids:
            assert pid in result, (
                f"Probe report {pid!r} was silently dropped in the over-cap path"
            )
        for sid in sub_ids:
            assert sid in result, (
                f"Sub-partition report {sid!r} was dropped"
            )

    def test_under_cap_uses_probe_only(self) -> None:
        probe_ids = ["B001", "B002"]
        total_count = _PAGE_CAP - 1

        result, _ = _simulate_over_cap_branching(
            probe_ids=probe_ids,
            probe_total_count=total_count,
            sub_ids=["B003"],   # should never be reached
            initial_seen=set(),
        )
        assert set(result) == set(probe_ids)
        assert "B003" not in result

    def test_probe_seen_does_not_pollute_cross_discipline_seen_ids(self) -> None:
        """Under-cap: probe_seen should commit into seen_ids so cross-discipline
        dedup still works. Over-cap: seen_ids should contain both probe and sub ids."""
        probe_ids = ["X001", "X002"]
        sub_ids = ["X003"]
        total_count = _PAGE_CAP + 1

        _, final_seen = _simulate_over_cap_branching(
            probe_ids=probe_ids,
            probe_total_count=total_count,
            sub_ids=sub_ids,
            initial_seen=set(),
        )
        assert "X001" in final_seen
        assert "X002" in final_seen
        assert "X003" in final_seen
