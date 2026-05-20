"""Polymarket watchlist — single source of truth for streaming + alerts + snapshot.

The watchlist YAML at ``C:\\IMDR_LOCAL\\polymarket\\watchlist.yml`` is the
contract consumed by:

* ``streaming.py`` — polls every concrete (non-wildcard, non-pruned) slug.
* ``polywatch.py`` — uses ``slug -> asset_tag`` to group alert emails.
* ``macro_snapshot.py`` — renders curated rows using the editorial fields
  (``section``, ``label``, ``asset``, ``market_read``, ``event_date``,
  ``event_id``).

Schema (per event entry):

    slug:           required. Polymarket event slug. Suffix ``*`` enables
                    prefix matching for markets Polymarket hasn't posted yet
                    (e.g. ``how-many-jobs-added-in-may-*``). Wildcard slugs
                    are skipped by polling consumers; ``macro_snapshot``
                    resolves them via prefix LIKE against observations.db.
    asset_tag:      required. ``[a-z0-9_]+``. Drives polywatch grouping.
    section:        optional. Macro-snapshot section title.
    label:          optional. Macro-snapshot row label.
    asset:          optional. Macro-snapshot asset pill text.
    market_read:    optional. Editorial commentary.
    event_date:     optional ISO date. Underlying release/decision date —
                    used for forward/resolved classification in the snapshot.
    event_id:       optional int. Polymarket numeric ID; preferred over slug
                    when present.
    pruned:         optional bool. Set by ``streaming prune --apply`` once a
                    slug is dead/missing on Polymarket. Entries stay in YAML
                    for audit history but are filtered out on load.
    pruned_at:      optional ISO date. When the entry was pruned.
    pruned_reason:  optional str. ``MISSING`` | ``DEAD`` | ``ERROR``.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import yaml


POLY_DIR = Path(r"C:\IMDR_LOCAL\polymarket")
WATCHLIST_FILE = POLY_DIR / "watchlist.yml"

# Concrete slug: lower-case alphanumerics + hyphens. Trailing '*' enables
# prefix match (snapshot-only); polling consumers skip wildcard entries.
_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]*\*?$")
_ASSET_TAG_RE = re.compile(r"^[a-z0-9_]+$")
_PRUNED_REASONS = frozenset({"MISSING", "DEAD", "ERROR"})

DEFAULT_ASSET_TAG = "uncurated"


class WatchlistError(ValueError):
    """Raised when watchlist.yml fails validation."""


@dataclass(frozen=True)
class WatchlistEntry:
    slug: str
    asset_tag: str
    section: str | None = None
    label: str | None = None
    asset: str | None = None
    market_read: str | None = None
    event_date: date | None = None
    event_id: int | None = None
    pruned: bool = False
    pruned_at: date | None = None
    pruned_reason: str | None = None

    @property
    def is_wildcard(self) -> bool:
        return self.slug.endswith("*")

    @property
    def has_snapshot_meta(self) -> bool:
        return bool(self.section and self.label and self.asset)


def _coerce_date(value: object, field_name: str, slug: str) -> date | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError as e:
            raise WatchlistError(
                f"watchlist entry {slug!r}: {field_name} must be ISO date (YYYY-MM-DD), got {value!r}"
            ) from e
    raise WatchlistError(
        f"watchlist entry {slug!r}: {field_name} must be a date string, got {type(value).__name__}"
    )


def _build_entry(raw: dict, *, line_no: int) -> WatchlistEntry:
    if not isinstance(raw, dict):
        raise WatchlistError(f"watchlist entry #{line_no}: expected mapping, got {type(raw).__name__}")

    slug = raw.get("slug")
    if not isinstance(slug, str) or not slug:
        raise WatchlistError(f"watchlist entry #{line_no}: missing required 'slug'")
    slug = slug.strip().lower()
    if not _SLUG_RE.match(slug):
        raise WatchlistError(
            f"watchlist entry {slug!r}: invalid slug; must match {_SLUG_RE.pattern}"
        )

    asset_tag = raw.get("asset_tag")
    if not isinstance(asset_tag, str) or not asset_tag:
        raise WatchlistError(f"watchlist entry {slug!r}: missing required 'asset_tag'")
    asset_tag = asset_tag.strip().lower()
    if not _ASSET_TAG_RE.match(asset_tag):
        raise WatchlistError(
            f"watchlist entry {slug!r}: invalid asset_tag {asset_tag!r}; must match {_ASSET_TAG_RE.pattern}"
        )

    event_id = raw.get("event_id")
    if event_id is not None and not isinstance(event_id, int):
        raise WatchlistError(f"watchlist entry {slug!r}: event_id must be int, got {type(event_id).__name__}")

    pruned_reason = raw.get("pruned_reason")
    if pruned_reason is not None:
        if not isinstance(pruned_reason, str) or pruned_reason not in _PRUNED_REASONS:
            raise WatchlistError(
                f"watchlist entry {slug!r}: pruned_reason must be one of {sorted(_PRUNED_REASONS)}"
            )

    return WatchlistEntry(
        slug=slug,
        asset_tag=asset_tag,
        section=raw.get("section"),
        label=raw.get("label"),
        asset=raw.get("asset"),
        market_read=raw.get("market_read"),
        event_date=_coerce_date(raw.get("event_date"), "event_date", slug),
        event_id=event_id,
        pruned=bool(raw.get("pruned", False)),
        pruned_at=_coerce_date(raw.get("pruned_at"), "pruned_at", slug),
        pruned_reason=pruned_reason,
    )


def load_watchlist(path: Path = WATCHLIST_FILE) -> list[WatchlistEntry]:
    """Read and validate the YAML watchlist; returns ALL entries (incl. pruned).

    Caller decides whether to filter out pruned entries (use ``active_slugs``
    or ``snapshot_entries`` for the common cases).
    """
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    if not isinstance(raw, dict):
        raise WatchlistError(f"{path}: top-level must be a mapping with an 'events' list")
    raw_events = raw.get("events", [])
    if not isinstance(raw_events, list):
        raise WatchlistError(f"{path}: 'events' must be a list")

    entries: list[WatchlistEntry] = []
    seen: set[str] = set()
    for i, item in enumerate(raw_events, 1):
        entry = _build_entry(item, line_no=i)
        if entry.slug in seen:
            raise WatchlistError(f"{path}: duplicate slug {entry.slug!r}")
        seen.add(entry.slug)
        entries.append(entry)
    return entries


def active_slugs(entries: list[WatchlistEntry]) -> list[str]:
    """Concrete (non-wildcard) slugs of non-pruned entries — the polling list."""
    return [e.slug for e in entries if not e.pruned and not e.is_wildcard]


def asset_tag_map(entries: list[WatchlistEntry]) -> dict[str, str]:
    """``slug -> asset_tag`` for non-pruned entries (polywatch grouping)."""
    return {e.slug: e.asset_tag for e in entries if not e.pruned}


def snapshot_entries(entries: list[WatchlistEntry]) -> list[WatchlistEntry]:
    """Non-pruned entries that have the editorial fields macro_snapshot needs."""
    return [e for e in entries if not e.pruned and e.has_snapshot_meta]


def mark_pruned(path: Path, prune_map: dict[str, str], today: date) -> int:
    """Set ``pruned/pruned_at/pruned_reason`` on entries whose slug is in ``prune_map``.

    Round-trips via PyYAML — comments are not preserved, but every meaningful
    datum lives in fields, so that's acceptable.

    Writes ``<path>.bak`` first; returns count of entries modified.
    """
    if not path.exists():
        raise FileNotFoundError(path)
    with path.open(encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    if not isinstance(raw, dict) or not isinstance(raw.get("events"), list):
        raise WatchlistError(f"{path}: malformed YAML, expected {{'events': [...]}}")

    today_str = today.isoformat()
    n_pruned = 0
    for entry in raw["events"]:
        if not isinstance(entry, dict):
            continue
        slug = (entry.get("slug") or "").strip().lower()
        reason = prune_map.get(slug)
        if reason is None:
            continue
        if entry.get("pruned"):
            continue  # already pruned, leave history alone
        entry["pruned"] = True
        entry["pruned_at"] = today_str
        entry["pruned_reason"] = reason
        n_pruned += 1

    if n_pruned == 0:
        return 0

    bak = path.with_name(path.name + ".bak")
    bak.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")

    with path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(
            raw,
            f,
            sort_keys=False,
            default_flow_style=False,
            allow_unicode=True,
            width=120,
        )
    return n_pruned
