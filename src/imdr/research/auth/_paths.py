"""Filesystem paths used by the research-auth module.

Two locations:

* **Profile dir** — Playwright ``user_data_dir``. One per vendor. Holds
  the live Chrome state (cookies, prefs, IndexedDB). Today's playground
  code stores these under ``playground/research/profiles/{vendor}/``;
  we keep that path so existing seeded profiles work without a one-off
  migration.
* **Snapshot dir** — JSON ``storage_state`` exports. One file per vendor.
  Lives under ``data/cache/research_auth/{vendor}/storage_state.json``,
  gitignored, intended as a portable rescue copy of cookies + origins
  data (localStorage, sessionStorage).
"""
from __future__ import annotations

from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[4]

PROFILE_ROOT = _PROJECT_ROOT / "playground" / "research" / "profiles"
SNAPSHOT_ROOT = _PROJECT_ROOT / "data" / "cache" / "research_auth"


def profile_dir(vendor: str) -> Path:
    """Return (and create) the Playwright user_data_dir for ``vendor``."""
    p = PROFILE_ROOT / vendor
    p.mkdir(parents=True, exist_ok=True)
    return p


def snapshot_path(vendor: str) -> Path:
    """Return the ``storage_state.json`` path for ``vendor``.

    Parent dir is created on demand; the file itself is created by
    Playwright when :meth:`BrowserContext.storage_state` is called.
    """
    d = SNAPSHOT_ROOT / vendor
    d.mkdir(parents=True, exist_ok=True)
    return d / "storage_state.json"
