"""Common types for the Korea govt-filings discovery layer."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path


@dataclass(slots=True, frozen=True)
class FilingItem:
    """One filing as discovered by a per-agency fetcher.

    Mirrors most of imdr.research.filings.FilingInput so the
    orchestrator can pass items straight through to ingest_filing()
    when migrations land. PDF bytes/text NOT included — fetched lazily
    at ingest time, not at discovery time.
    """

    vendor_code: str
    title: str
    publish_date: date
    source_url: str                   # canonical detail page or RSS link
    pdf_url: str | None = None
    doc_type: str = "release"         # release / minutes / report / outlook / speech / decision / review
    stream: str = ""                  # vendor-specific stream id
    extras: dict = field(default_factory=dict)  # source-specific raw fields

    def to_json(self) -> dict:
        d = asdict(self)
        d["publish_date"] = self.publish_date.isoformat()
        return d

    @classmethod
    def from_json(cls, d: dict) -> "FilingItem":
        return cls(
            vendor_code=d["vendor_code"],
            title=d["title"],
            publish_date=date.fromisoformat(d["publish_date"]),
            source_url=d["source_url"],
            pdf_url=d.get("pdf_url"),
            doc_type=d.get("doc_type", "release"),
            stream=d.get("stream", ""),
            extras=d.get("extras", {}),
        )


@dataclass(slots=True)
class FetchResult:
    """What a fetch_X.discover() returns. Distinguishes fetch failure from
    'fetched cleanly, 0 items today' — both are valid daily outcomes."""

    vendor_code: str
    ok: bool
    items: list[FilingItem] = field(default_factory=list)
    error: str | None = None
    note: str = ""    # human-readable extra context for the daily report


# Rolling seen.json — content-hash-keyed dedup across daily runs.
# The orchestrator compares fetched items against this set and writes
# only the unseen ones to the daily snapshot.
SEEN_FILE = Path(__file__).parent / "data" / "seen.json"


def load_seen() -> set[str]:
    if not SEEN_FILE.exists():
        return set()
    data = json.loads(SEEN_FILE.read_text(encoding="utf-8"))
    return set(data.get("seen", []))


def save_seen(seen: set[str]) -> None:
    SEEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    SEEN_FILE.write_text(
        json.dumps({"seen": sorted(seen)}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def dedup_key(item: FilingItem) -> str:
    """Stable key used both for seen.json and for the eventual
    research.dim_report uniqueness check. Source URL is the natural
    primary key for govt filings since (vendor, date, title) sometimes
    collides on repeated boilerplate notices (e.g. MSB Issuance Notices)."""
    return f"{item.vendor_code}|{item.source_url}"
