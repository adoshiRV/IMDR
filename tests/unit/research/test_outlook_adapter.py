"""Unit tests for the Outlook email source-adapter (route B prototype).

Covers the HTML sanitizer, the synthetic-Document builder, the
folder->vendor map, the CBA classifier, and the dedup decision.
"""
from __future__ import annotations

import hashlib
import sys
from datetime import date
from pathlib import Path
from types import SimpleNamespace

_PR = Path(__file__).resolve().parents[3] / "playground" / "research"
if str(_PR) not in sys.path:
    sys.path.insert(0, str(_PR))

from ingest.crawler_outlook import (  # noqa: E402
    EMAIL_VENDOR_HOLD,
    FOLDER_TO_VENDOR,
    OutlookReportRef,
    _derive_source_type,
    decide_dedup,
    discover_reports,
    email_noise_reason,
)
from ingest.email_doc import (  # noqa: E402
    EMAIL_PARSER_VERSION,
    sanitize_email_html,
    synthesize_document,
)
from ingest.classifiers import cba, email_common  # noqa: E402


# ─── HTML sanitizer ──────────────────────────────────────────────────────
def test_sanitizer_strips_caution_banner_and_keeps_body():
    html = (
        "<table><tr><td><p><b>CAUTION: External email. Do not click links "
        "or open attachments unless you recognize the sender.</b></p></td></tr></table>"
        "<div><p>Wage growth remains steady at 0.8%/qtr.</p>"
        "<p>The RBA is expected to hold the cash rate.</p></div>"
    )
    out = sanitize_email_html(html)
    assert "CAUTION: External email" not in out
    assert "Wage growth remains steady at 0.8%/qtr." in out
    assert "RBA is expected to hold the cash rate." in out


def test_sanitizer_cuts_trailing_disclaimer():
    html = (
        "<p>SGS continue to outperform in Asia.</p>"
        "<p>Things you should know</p>"
        "<p>The information presented in this email is an extract...</p>"
        "<p>This email was sent to: research@rvcapital.com</p>"
    )
    out = sanitize_email_html(html)
    assert "SGS continue to outperform in Asia." in out
    assert "Things you should know" not in out
    assert "This email was sent to" not in out


def test_sanitizer_handles_empty():
    assert sanitize_email_html("") == ""


# ─── synthetic Document ──────────────────────────────────────────────────
def test_synthesize_document_fields_and_hash():
    text = "BI hiked 25bps to 5.5% to stem IDR depreciation. SRBI 1Y at 7.68%."
    doc = synthesize_document(text)
    assert doc.full_text == text
    assert doc.page_count == 1
    assert doc.pages_text == (text,)
    assert doc.parser_version == EMAIL_PARSER_VERSION
    assert doc.content_hash == hashlib.sha256(text.encode("utf-8")).digest()
    assert doc.pdf_bytes == b""


# ─── folder -> vendor map ────────────────────────────────────────────────
def test_folder_vendor_map():
    assert FOLDER_TO_VENDOR["GS"] == "goldman"
    assert FOLDER_TO_VENDOR["CBA"] == "cba"
    assert FOLDER_TO_VENDOR["Citi"] == "citi"
    assert FOLDER_TO_VENDOR["Nom"] == "nomura"
    assert FOLDER_TO_VENDOR["BOFA"] == "bofa"
    assert FOLDER_TO_VENDOR["Westpac"] == "westpac"
    assert FOLDER_TO_VENDOR["CACIB"] == "cacib"
    # SCB (desk) and STANC (formal research) are two folders, one vendor.
    assert FOLDER_TO_VENDOR["SCB"] == "stanc"
    assert FOLDER_TO_VENDOR["STANC"] == "stanc"
    assert len(FOLDER_TO_VENDOR) == 16


# ─── CBA classifier ──────────────────────────────────────────────────────
def _cba_ref():
    return SimpleNamespace(
        title="CBA Economics: Update - CBA Wage and Labour Insights – May 2026",
        body_html="<p>In May, CBA Wage Insights showed wage growth steady at 0.8%/qtr. "
                  "The RBA held the cash rate; unemployment at 4.3%. WPI growth to lift.</p>",
        body_text_summary="Wage growth steady; RBA on hold; unemployment 4.3%.",
        sender_name="Harry Ottley",
        publish_date=date(2026, 6, 11),
        vendor_code="cba",
        source_type="research",
    )


def test_cba_classify_macro_australia():
    result = cba.classify(_cba_ref())
    assert result.asset_class == "MACRO"
    assert result.country_code == "AU"
    assert ("country", "AU") in {(t.category, t.value) for t in result.tags}


def test_email_classify_citi_desk_rates_indonesia():
    ref = SimpleNamespace(
        title="Citi Macro - SRBI...the new golden child in Asia?",
        body_html="<p>BI surprise 25bps hike to 5.5% to stem IDR depreciation. "
                  "SRBI 1Y 7.68%, 9M 7.46%. Indonesia IndoGB 5y fair value 7.3-7.7%. "
                  "FX concessionary swap; bond yields; curve; bps pickup. "
                  "Strong interest from offshore Asia real money.</p>",
        body_text_summary="",
        sender_name="Zeke Koh",
        publish_date=date(2026, 6, 11),
        vendor_code="citi",
        source_type="desk_commentary",
    )
    result = email_common.classify_email(ref, vendor_code="citi")
    assert result.asset_class == "RATES"
    assert result.country_code == "ID"
    assert ("region", "apac") in {(t.category, t.value) for t in result.tags}


# ─── dedup decision ──────────────────────────────────────────────────────
def _ref(imi: str) -> OutlookReportRef:
    return OutlookReportRef(
        url="g", pdf_url="g", uuid=imi, title="t", publish_date=date(2026, 6, 11),
        vendor_code="citi", folder="Citi", archetype="desk_commentary",
        source="email", source_type="desk_commentary", internet_message_id=imi,
    )


def test_dedup_skips_duplicate_message_id():
    action, reason = decide_dedup(
        _ref("<a@x>"), "synthetic_body", b"\x01" * 32,
        seen_message_ids={"<a@x>"}, known_content_hashes=set(),
    )
    assert action == "skip"
    assert "internet_message_id" in reason


def test_dedup_skips_pure_wrapper():
    action, reason = decide_dedup(
        _ref("<b@x>"), "skip", None,
        seen_message_ids=set(), known_content_hashes=set(),
    )
    assert action == "skip"
    assert "wrapper" in reason


def test_dedup_skips_portal_pointer():
    # build_email_document returns "skip(portal_pointer)" for teaser cover-notes.
    action, reason = decide_dedup(
        _ref("<pp@x>"), "skip(portal_pointer)", None,
        seen_message_ids=set(), known_content_hashes=set(),
    )
    assert action == "skip"
    assert "portal-link pointer" in reason


def test_dedup_skips_known_pdf_hash():
    h = b"\x02" * 32
    action, reason = decide_dedup(
        _ref("<c@x>"), "pdf", h,
        seen_message_ids=set(), known_content_hashes={h},
    )
    assert action == "skip"
    assert "portal copy" in reason


# ─── lenient email noise gate ────────────────────────────────────────────
def test_email_noise_drops_admin_and_media():
    assert email_noise_reason("Asia Research Webcast Timetable") == "webcast"
    assert email_noise_reason("On Clients' Minds: Most Read Global Macro Research") == "most_read_digest"
    assert email_noise_reason("Video: Asia Chart of the Week") == "media"
    assert email_noise_reason("Global Economic Calendar : 15 June - 21 June") == "calendar"
    assert email_noise_reason("Extel Survey Closing TODAY") == "survey"
    assert email_noise_reason("Three Actionable Ideas: X - OW | Y - UW") == "single_name_ideas"


def test_email_noise_drops_chartpacks():
    # Chart-pack pointers are link-only (substance in unreachable chart PDFs).
    assert email_noise_reason("AUD Rates Morning Chartpacks - 19 June 2026") == "chartpack"
    assert email_noise_reason("Equity Chart Pack") == "chartpack"


def test_email_noise_keeps_real_research():
    # No single-name-equity filtering on the email path — real notes survive.
    assert email_noise_reason("[/] DB Asia: Indonesia - BI surprise hike") is None
    assert email_noise_reason("Citi Macro - SRBI...the new golden child in Asia?") is None
    assert email_noise_reason("CBA Economics: RBA in June - no change expected") is None
    assert email_noise_reason("India: engineering BoP stability, not cure") is None
    # Substantive daily series must NOT be caught by the chartpack rule
    # (verified from real bodies 2026-06-22 — these carry full market text).
    assert email_noise_reason("Australian Morning Focus") is None
    assert email_noise_reason("FinanceAM") is None


def test_email_noise_drops_login_and_otp():
    # Real vendor-portal verification/login mail (sampled 2026-06-18).
    assert email_noise_reason("UBS Neo Login | 610383 is your login code") == "login_code"
    assert email_noise_reason("343365 is your Polymarket login code") == "login_code"
    assert email_noise_reason("BARX FX Installation and OTP Access Guide") == "otp"
    assert email_noise_reason("Verify your email to continue") == "account_verification"
    assert email_noise_reason("Reset your password") == "password_reset"
    assert email_noise_reason(
        "Nomura Global Research Portal: New Features and Recent Enhancements"
    ) == "portal_admin"
    # Folder-pass additions (Westpac/CACIB/STANC sampled 2026-06-18).
    assert email_noise_reason("Video Views – EM rates – Opportunities (replay)") == "media"
    assert email_noise_reason("Crédit Agricole CIB Research WEBSITE - SIGN UP!") == "marketing"
    assert email_noise_reason("Global Research: Top Weekly Reads – 6 – 12 June 2026") == "most_read_digest"
    # Admin credential/token mail confirmed in the bank-by-bank smoke test.
    assert email_noise_reason("Mercury Portal Token") == "portal_token"
    assert email_noise_reason("Your Mercury Portal Token: 28437859") == "portal_token"
    assert email_noise_reason("Your JPMM username and login details") == "credentials"
    assert email_noise_reason("JPMM Markets: your new password") == "credentials"


def test_email_noise_does_not_drop_tokenisation_research():
    # Guard: the login/OTP patterns deliberately avoid bare "token" so
    # digital-asset / tokenisation research is never dropped.
    assert email_noise_reason("Tokenisation of Indonesian government bonds") is None
    assert email_noise_reason("Crypto & digital token markets: a primer") is None
    assert email_noise_reason("Korea rates: the curve steepening code") is None


# ─── source_type sender heuristic ────────────────────────────────────────
def test_source_type_research_alias():
    rec = {"sender": {"address": "macro@alerts.publishing.gs.com"},
           "subject": "China: Three things in China"}
    assert _derive_source_type(rec, "portal_digest") == "research"


def test_source_type_desk_person_at_desk_domain():
    rec = {"sender": {"address": "walter.wong@db.com"},
           "subject": "[/] DB Asia: Korea - BoK - Hawkish Hold"}
    assert _derive_source_type(rec, "html_note") == "desk_commentary"


def test_source_type_cba_analyst_is_research():
    rec = {"sender": {"address": "harry.ottley@cba.com.au"},
           "subject": "CBA Economics: Update - Wage and Labour Insights"}
    assert _derive_source_type(rec, "attached_pdf") == "research"


def test_source_type_bofa_folder_default_desk():
    # BofA folder is 100% sales/trading commentary; bofa.com is NOT a desk
    # domain, so without a folder default it would wrongly default research.
    rec = {"sender": {"address": "vivian.liang2@bofa.com"},
           "subject": "Asia FX Midweek Focus"}
    assert _derive_source_type(rec, "html_note", vendor="bofa") == "desk_commentary"
    # Resolves the vendor from the folder name too.
    rec2 = {"sender": {"address": "jamshed.d.sidhva@bofa.com"},
            "subject": "Arvin The: Asia G10 Spot Views #1234", "folder": "BOFA"}
    assert _derive_source_type(rec2, "html_note") == "desk_commentary"


def test_source_type_nomura_research_forward_not_desk():
    # Whole Nomura folder forwarded by one salesperson; a research forward
    # (no desk-subject marker) must default to research, not desk.
    rec = {"sender": {"address": "remo.winkelmolen@nomura.com"},
           "subject": "USD Rates Weekly Outlook", "folder": "Nom"}
    assert _derive_source_type(rec, "html_note") == "research"


def test_source_type_nomura_desk_product_still_desk():
    # A genuine Nomura desk product keeps desk via the desk-subject rule.
    rec = {"sender": {"address": "remo.winkelmolen@nomura.com"},
           "subject": "US Rates Desk Strategy (Jon Cohn)", "folder": "Nom"}
    assert _derive_source_type(rec, "html_note") == "desk_commentary"


def test_source_type_scb_vs_stanc_split():
    # Same vendor (stanc), two folders, opposite source_types.
    # STANC formal research alias -> research (must beat the sc.com
    # person-at-desk-domain heuristic).
    stanc = {"sender": {"address": "research.distribution@sc.com"},
             "subject": "The Morning Standard – BoJ – If not now, when?",
             "folder": "STANC"}
    assert _derive_source_type(stanc, "html_note") == "research"
    # SCB desk commentary from a personal sc.com sender -> desk.
    scb = {"sender": {"address": "john.szto@sc.com"},
           "subject": "SCB (India Rates) - belly cheapening", "folder": "SCB"}
    assert _derive_source_type(scb, "html_note") == "desk_commentary"


def test_source_type_westpac_and_cacib_default_research():
    # Vendor default BEATS a body-only "desk_commentary" archetype: these
    # are formal economist/strategist notes that happen to lack a PDF.
    wp = {"sender": {"address": "financialmarkets@email6.westpac.com.au"},
          "subject": "FOMC ready to weather economic uncertainty"}
    assert _derive_source_type(wp, "desk_commentary", vendor="westpac") == "research"
    ca = {"sender": {"address": "noreply-cacibresearch@ca-cib.com"},
          "subject": "FX Daily - USD: Warsh and go"}
    assert _derive_source_type(ca, "desk_commentary", vendor="cacib") == "research"
    # But bofa's default is desk, regardless of archetype.
    bo = {"sender": {"address": "vivian.liang2@bofa.com"}, "subject": "Asia FX Midweek Focus"}
    assert _derive_source_type(bo, "html_note", vendor="bofa") == "desk_commentary"


def test_source_type_body_disclaimer_overrides_research_default():
    # Body "NOT RESEARCH" disclaimer is authoritative even for a vendor
    # whose folder default is research.
    rec = {"sender": {"address": "harry.ottley@cba.com.au"},
           "subject": "CBA desk note",
           "body_html": "<p>This is a sales note and not a product of research.</p>"}
    assert _derive_source_type(rec, "attached_pdf", vendor="cba") == "desk_commentary"


def test_discover_holds_cba_and_cacib(tmp_path):
    import json as _json

    def _write(vendor, slug):
        d = tmp_path / vendor
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{slug}.json").write_text(_json.dumps({
            "internet_message_id": f"<{slug}@x>",
            "subject": f"{vendor} macro note",
            "received": "2026-06-18T00:00:00Z",
            "folder": "",
            "vendor_code": vendor,
            "body_html": "<p>" + "macro " * 60 + "</p>",
        }), encoding="utf-8")

    _write("cba", "a")
    _write("cacib", "b")
    _write("citi", "c")

    # Default run: cba + cacib are held out, citi flows through.
    got = {r.vendor_code for r in discover_reports(tmp_path)}
    assert "citi" in got
    assert "cba" not in got and "cacib" not in got
    # Explicit --vendors request overrides the hold (for later onboarding).
    assert {r.vendor_code for r in discover_reports(tmp_path, vendors=["cba"])} == {"cba"}
    assert EMAIL_VENDOR_HOLD == frozenset({"cba", "cacib"})


def test_dedup_ingests_new_body():
    action, reason = decide_dedup(
        _ref("<d@x>"), "synthetic_body", b"\x03" * 32,
        seen_message_ids=set(), known_content_hashes=set(),
    )
    assert action == "ingest"
    assert reason == ""
