"""PostToolUse hook: auto-check Spider digest calendars are date-sorted.

Wired in settings.json as a PostToolUse hook on Write|Edit. Reads the hook JSON
on stdin, and if the edited file is a Spider digest markdown (daily or weekly),
runs the calendar date-sort check. On a violation it exits 2 with a stderr
message so Claude Code surfaces it and Claude fixes the ordering before locking /
rendering. Silent (exit 0) for every non-digest file and for clean digests.

See `.claude/agents/spider.md` hard rule 5 and `check_calendar_sort.py`.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))


def _is_digest(p: Path) -> bool:
    if p.suffix.lower() != ".md":
        return False
    posix = p.as_posix().lower()
    name = p.name.lower()
    # Spider digest MDs live under data/research_summary/{daily,weekly}/...
    if "/research_summary/" in posix and ("/daily/" in posix or "/weekly/" in posix):
        return True
    # or match the known digest stems anywhere
    return "spider" in name and any(k in name for k in ("digest", "pm-note", "daily", "weekly"))


def main() -> int:
    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0
    ti = data.get("tool_input", {}) or {}
    fp = ti.get("file_path") or ti.get("path") or ""
    if not fp:
        return 0
    p = Path(fp)
    if not _is_digest(p) or not p.exists():
        return 0
    try:
        from check_calendar_sort import check_file
        violations = check_file(p, quiet=True)
    except Exception as e:  # never let the hook break a write
        print(f"[calendar-sort] check skipped ({e})", file=sys.stderr)
        return 0
    if not violations:
        return 0
    print(
        f"[calendar-sort] {p.name}: {len(violations)} calendar row(s) OUT OF DATE ORDER "
        f"— every Date/When/Time table must be chronological (spider.md rule 5). "
        f"Fix before locking/rendering. Details:",
        file=sys.stderr,
    )
    for v in violations[:12]:
        print(v, file=sys.stderr)
    print(
        f'Re-check with: python scripts/research/check_calendar_sort.py "{fp}"',
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
