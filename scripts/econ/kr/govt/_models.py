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


# Runtime state lives under the canonical ``data/`` tree, NOT alongside
# the source code. State is partitioned per-agency so each vendor maps
# to one folder — same shape as the per-vendor SharePoint mirror
# (econ/kr/{vendor}/) and the existing data/econ/{vendor}/ convention
# (kosis, reb, bi, bps, ...). Created on first run; gitignored via the
# top-level ``data/*`` rule.
#
#   data/econ/kr/govt/
#     _last_run.log                — orchestrator stdout (cross-vendor)
#     {vendor}/
#       seen.json                  — rolling source_url dedup
#       snapshots/{YYYY-MM-DD}.json — per-day new-items manifest
#
# load_seen() / save_seen() keep a flat-set API (one big set keyed by
# dedup_key = "{vendor}|{source_url}") so the orchestrator doesn't care
# about partitioning. The on-disk split happens at IO time.
_REPO_ROOT = Path(__file__).resolve().parents[4]
DATA_DIR = _REPO_ROOT / "data" / "econ" / "kr" / "govt"


def vendor_dir(vendor_code: str) -> Path:
    """Per-vendor runtime-state directory."""
    return DATA_DIR / vendor_code


def vendor_seen_file(vendor_code: str) -> Path:
    return vendor_dir(vendor_code) / "seen.json"


def vendor_snapshots_dir(vendor_code: str) -> Path:
    return vendor_dir(vendor_code) / "snapshots"


def load_seen() -> set[str]:
    """Load every per-vendor seen.json into one flat set of dedup_keys."""
    out: set[str] = set()
    if not DATA_DIR.exists():
        return out
    for sub in sorted(DATA_DIR.iterdir()):
        if not sub.is_dir():
            continue
        f = sub / "seen.json"
        if not f.exists():
            continue
        try:
            payload = json.loads(f.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        vendor = sub.name
        for url in payload.get("seen", []):
            out.add(f"{vendor}|{url}")
    return out


def save_seen(seen: set[str]) -> None:
    """Partition the flat set by vendor and write one seen.json per agency."""
    by_vendor: dict[str, set[str]] = {}
    for key in seen:
        if "|" not in key:
            continue
        vendor, url = key.split("|", 1)
        by_vendor.setdefault(vendor, set()).add(url)
    for vendor, urls in by_vendor.items():
        path = vendor_seen_file(vendor)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({"seen": sorted(urls)}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


def dedup_key(item: FilingItem) -> str:
    """Stable key used both for seen.json and for the eventual
    research.dim_report uniqueness check. Source URL is the natural
    primary key for govt filings since (vendor, date, title) sometimes
    collides on repeated boilerplate notices (e.g. MSB Issuance Notices)."""
    return f"{item.vendor_code}|{item.source_url}"
