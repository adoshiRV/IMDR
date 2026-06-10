"""Common types for the Australia govt-filings prod layer.

Mirror of `scripts/econ/kr/govt/_models.py` — per-vendor partitioned
runtime state under `data/econ/au/govt/{vendor}/`. Same `FilingItem` /
`FetchResult` / `dedup_key` contract so the daily orchestrator can
pass items through to `imdr.research.filings.ingest_filing` identically
to Korea.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path


@dataclass(slots=True, frozen=True)
class FilingItem:
    """One filing as discovered by a per-agency fetcher.

    PDF bytes / body text NOT included here — resolved lazily at ingest
    time via `resolvers.resolve(item)`.
    """

    vendor_code: str
    title: str
    publish_date: date
    source_url: str
    pdf_url: str | None = None
    doc_type: str = "release"
    stream: str = ""
    extras: dict = field(default_factory=dict)

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
    vendor_code: str
    ok: bool
    items: list[FilingItem] = field(default_factory=list)
    error: str | None = None
    note: str = ""


# Per-vendor partitioned runtime state under data/econ/au/govt/{vendor}/
#   data/econ/au/govt/
#     _last_run.log                  — orchestrator stdout (cross-vendor)
#     {vendor}/
#       seen.json                    — rolling source_url dedup
#       snapshots/{YYYY-MM-DD}.json   — per-day new-items manifest
#
# load_seen() / save_seen() keep a flat-set API keyed by
# dedup_key = "{vendor}|{source_url}"; the on-disk split happens at IO time.
_REPO_ROOT = Path(__file__).resolve().parents[4]
DATA_DIR = _REPO_ROOT / "data" / "econ" / "au" / "govt"


def vendor_dir(vendor_code: str) -> Path:
    return DATA_DIR / vendor_code


def vendor_seen_file(vendor_code: str) -> Path:
    return vendor_dir(vendor_code) / "seen.json"


def vendor_snapshots_dir(vendor_code: str) -> Path:
    return vendor_dir(vendor_code) / "snapshots"


def load_seen() -> set[str]:
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
    return f"{item.vendor_code}|{item.source_url}"
