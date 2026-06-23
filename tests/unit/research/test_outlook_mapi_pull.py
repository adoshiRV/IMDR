"""Unit tests for the route-C local Outlook MAPI/COM producer.

Covers the pure field-mapping logic with **mocked COM objects** (duck-typed
``SimpleNamespace`` — no live Outlook): slug/imi8 scheme, content-type guess,
the real-PDF discriminator (must NOT use the inline flag — DB attaches real PDFs
with a content-id, P0 §4.4), EX->SMTP resolution, the ReceivedTime UTC fix
(pywin32 mislabels host-local as +00:00), and ``build_record`` end-to-end.
"""
from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path
from types import SimpleNamespace

_PR = Path(__file__).resolve().parents[3] / "playground" / "research"
if str(_PR) not in sys.path:
    sys.path.insert(0, str(_PR))

from outlook import outlook_mapi_pull as mp  # noqa: E402

PR_IMI = mp.PR_INTERNET_MESSAGE_ID
PR_SMTP = mp.PR_SMTP_ADDRESS
PR_CID = mp.PR_ATTACH_CONTENT_ID


class FakePropAccessor:
    def __init__(self, props: dict):
        self._props = props

    def GetProperty(self, tag):  # noqa: N802
        if tag in self._props:
            return self._props[tag]
        raise RuntimeError(f"prop {tag} not set")


def _att(name, *, type_=mp.OL_BY_VALUE, size=100_000, cid=False):
    return SimpleNamespace(
        FileName=name, Type=type_, Size=size,
        PropertyAccessor=FakePropAccessor({PR_CID: "cid123"} if cid else {}),
    )


def _recip(name, address, rtype, addr_type="SMTP"):
    return SimpleNamespace(
        Name=name, Address=address, Type=rtype,
        AddressEntry=SimpleNamespace(Type=addr_type),
        PropertyAccessor=FakePropAccessor({PR_SMTP: address}),
    )


# ─── pure helpers ────────────────────────────────────────────────────────
def test_slug_and_imi8():
    assert mp._slug("[/] DB JPY Market PM Summary ") == "db_jpy_market_pm_summary"
    assert mp._slug("") == "untitled"
    h = mp._imi8("<abc@def.com>")
    assert len(h) == 8 and h == mp._imi8("<abc@def.com>")  # deterministic


def test_content_type_guess():
    assert mp._content_type("x.pdf") == "application/pdf"
    assert mp._content_type("logo.PNG") == "image/png"
    assert mp._content_type("weird.xyz") == "application/octet-stream"


def test_is_real_pdf_ignores_inline_flag():
    # The DB-PM case: a real .pdf flagged inline (content-id) is STILL a report.
    assert mp._is_real_pdf(_att("report.pdf", cid=True)) is True
    assert mp._is_real_pdf(_att("report.pdf", cid=False)) is True


def test_is_real_pdf_rejects_images_and_tiny():
    assert mp._is_real_pdf(_att("image001.png", cid=True)) is False
    assert mp._is_real_pdf(_att("sig.pdf", size=512)) is False  # below MIN_PDF_BYTES
    assert mp._is_real_pdf(_att("embedded.pdf", type_=5)) is False  # not by-value


def test_smtp_resolves_ex_passes_smtp():
    ex_obj = SimpleNamespace(PropertyAccessor=FakePropAccessor({PR_SMTP: "real@db.com"}))
    assert mp._smtp("/O=EXCHANGE/CN=...", "EX", ex_obj) == "real@db.com"
    assert mp._smtp("plain@db.com", "SMTP", ex_obj) == "plain@db.com"


def test_received_utc_discards_bogus_tzinfo():
    # pywin32 hands back host-local wall-clock mislabeled +00:00; the fixer must
    # discard that label and reinterpret as host-local before converting to UTC.
    bogus = dt.datetime(2026, 6, 22, 14, 25, 17, tzinfo=dt.timezone.utc)
    out = mp._received_utc(bogus)
    assert out.endswith("Z")
    expected = (dt.datetime(2026, 6, 22, 14, 25, 17)
                .replace(tzinfo=mp._HOST_TZ)
                .astimezone(dt.timezone.utc)
                .strftime("%Y-%m-%dT%H:%M:%SZ"))
    assert out == expected


# ─── build_record end-to-end (mocked COM mail item) ──────────────────────
def _fake_mail():
    return SimpleNamespace(
        Class=mp.OL_MAILITEM,
        EntryID="ENTRY123",
        Subject="[/] DB JPY Market PM Summary ",
        SenderName="Maki Hanawa",
        SenderEmailAddress="maki.hanawa@db.com",
        SenderEmailType="SMTP",
        ReceivedTime=dt.datetime(2026, 6, 22, 14, 25, 17, tzinfo=dt.timezone.utc),
        HTMLBody="<p>JGBs rallied; curve steepened 2.5bp in 10-30s.</p>",
        PropertyAccessor=FakePropAccessor({PR_IMI: "<msg42@db.com>"}),
        Recipients=[_recip("macrobox", "macrobox@list.db.com", mp.OL_TO),
                    _recip("Walter", "walter@db.com", mp.OL_CC)],
        Attachments=[_att("image001.gif", size=600, cid=True),
                     _att("DB JPY PM Summary.pdf", size=97_000, cid=True)],
    )


def test_build_record_maps_all_fields(tmp_path):
    rec = mp.build_record(_fake_mail(), "DB", "db",
                          vendor_dir=tmp_path / "db", save_attachments=False)
    assert rec["internet_message_id"] == "<msg42@db.com>"
    assert rec["graph_id"] == "ENTRY123"
    assert rec["folder"] == "DB" and rec["vendor_code"] == "db"
    assert rec["sender"] == {"name": "Maki Hanawa", "address": "maki.hanawa@db.com"}
    assert [r["address"] for r in rec["to"]] == ["macrobox@list.db.com"]
    assert [r["address"] for r in rec["cc"]] == ["walter@db.com"]
    assert rec["received"].endswith("Z")
    assert rec["body_content_type"] == "html"
    # the real PDF is recorded with a mapped `file`; the inline gif is not
    pdf = next(a for a in rec["attachments"] if a["name"].endswith(".pdf"))
    gif = next(a for a in rec["attachments"] if a["name"].endswith(".gif"))
    assert pdf.get("file", "").startswith("attachments/") and pdf["file"].endswith(".pdf")
    assert "file" not in gif and gif["is_inline"] is True


def test_build_record_saves_pdf_bytes(tmp_path, monkeypatch):
    saved = {}
    pdf_att = _att("DB JPY PM Summary.pdf", size=97_000, cid=True)
    pdf_att.SaveAsFile = lambda path: saved.setdefault("path", path)
    mail = _fake_mail()
    mail.Attachments = [pdf_att]
    rec = mp.build_record(mail, "DB", "db",
                          vendor_dir=tmp_path / "db", save_attachments=True)
    assert "path" in saved  # SaveAsFile was invoked
    assert Path(saved["path"]).is_absolute()  # Outlook needs an absolute path
    assert rec["attachments"][0]["file"].endswith(".pdf")
    assert "_pdf_unsaved" not in rec["attachments"][0]
