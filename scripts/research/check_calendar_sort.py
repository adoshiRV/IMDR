"""Calendar date-sort check for Spider digests (daily + weekly).

Scans one or more digest markdown files and verifies that every *calendar /
event table* is ordered chronologically. A calendar table is any GFM pipe
table whose header has a date-like column — one titled ``Date``, ``When`` or
``Time`` (case-insensitive). This covers, in the WEEKLY: the Tier-3 "Total
macro calendar", the Tier-1 §8 "This week" and §9 "The week ahead" grids, and
every per-country "This week & next week" board; and in the DAILY: any
day-ahead/week-ahead calendar or within-block event timeline.

Rows whose date cell can't be parsed (``—``, "*No scheduled releases*", pure
prose) are skipped, not failed. Date-range cells ("20-26 Jul", "27 Jul-02
Aug") and split cells ("07-29/30") sort on their FIRST date. Bucket markers
(②/③) and footnote superscripts are ignored.

Usage::

    python scripts/research/check_calendar_sort.py <digest.md> [<more.md> ...]

Exit code 0 = all calendar tables sorted; 1 = at least one out-of-order table
(or a bad path). Intended to be run before locking a digest MD and wired as a
PostToolUse hook on digest writes — see spider.md.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

_MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}
_MON = r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)"
_DATE_HEADERS = {"date", "when", "time"}
# a table with a date column but a NON-chronological first column (sorted by
# entity, not date) is a reference table, not a calendar — e.g. the source
# register (sorted by Bank). Skip those.
_NON_CAL_FIRST_COL = {
    "bank", "house", "desk", "market", "country", "#", "no", "leg", "tension",
    "region", "dimension", "indicator", "issuer", "name", "rank", "vendor",
}
# explicitly-soft date cells: intentionally undated, don't check ordering
_SOFT = ("tbc", "tbd", "outside window", "n/a")


def _date_key(cell: str):
    """Sortable (month, day, hour, minute) key from a date/when/time cell, or
    None if unparseable/soft. Ranges sort on their START date; split cells
    ("07-29/30") on the first date."""
    s = cell.strip()
    if not s or s in {"-", "—", "–"}:
        return None
    low = s.lower()
    if any(t in low for t in _SOFT):
        return None
    # range "DD-DD Mon" (shared trailing month, e.g. "20-26 Jul") -> first DD
    m = re.search(r"\b(\d{1,2})\s*[–—-]\s*\d{1,2}\s*" + _MON, s, re.I)
    if m:
        return (_MONTHS[m.group(2).lower()], int(m.group(1)), 0, 0)
    # "DD Mon" leftmost (also the start of "27 Jul-02 Aug", "Mon/Tue 14 Jul")
    m = re.search(r"\b(\d{1,2})\s*" + _MON, s, re.I)
    if m:
        return (_MONTHS[m.group(2).lower()], int(m.group(1)), 0, 0)
    # "Mon DD"
    m = re.search(_MON + r"[a-z]*\.?\s+(\d{1,2})", s, re.I)
    if m:
        return (_MONTHS[m.group(1).lower()], int(m.group(2)), 0, 0)
    # MM-DD (e.g. 07-29, 07-29/30 -> 07-29)
    m = re.search(r"\b(0[1-9]|1[0-2])-(\d{1,2})\b", s)
    if m:
        return (int(m.group(1)), int(m.group(2)), 0, 0)
    # month-name only ("~early Aug") -> day 0
    m = re.search(_MON, s, re.I)
    if m:
        return (_MONTHS[m.group(1).lower()], 0, 0, 0)
    # time only HH:MM (daily within-session timeline)
    m = re.search(r"\b([01]?\d|2[0-3]):([0-5]\d)\b", s)
    if m:
        return (0, 0, int(m.group(1)), int(m.group(2)))
    return None


def _cells(row: str):
    return [c.strip() for c in row.strip().strip("|").split("|")]


def _tables(lines):
    """Yield (header_line_no, header_cells, [(row_line_no, cells), ...])."""
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        if line.lstrip().startswith("|") and i + 1 < n and re.match(r"\s*\|[\s:|-]+\|?\s*$", lines[i + 1]):
            header = _cells(line)
            data = []
            j = i + 2
            while j < n and lines[j].lstrip().startswith("|"):
                data.append((j + 1, _cells(lines[j])))
                j += 1
            yield i + 1, header, data
            i = j
        else:
            i += 1


def check_file(path: Path, quiet: bool = False) -> list[str]:
    """Return a list of violation messages (empty = all good)."""
    text = path.read_text(encoding="utf-8")
    lines = text.split("\n")
    violations: list[str] = []
    n_cal = 0
    for hline, header, data in _tables(lines):
        col = next(
            (k for k, h in enumerate(header)
             if h.lower().strip("* ") in _DATE_HEADERS),
            None,
        )
        if col is None:
            continue
        # skip reference tables that carry a Date column but are sorted by an
        # entity (e.g. the source register, sorted by Bank), not chronologically
        if header and header[0].lower().strip("* ") in _NON_CAL_FIRST_COL:
            continue
        n_cal += 1
        keys = []
        for lno, cells in data:
            if col >= len(cells):
                continue
            k = _date_key(cells[col])
            if k is not None:
                keys.append((k, lno, cells[col]))
        for a, b in zip(keys, keys[1:]):
            if b[0] < a[0]:
                violations.append(
                    f"  L{b[1]}: '{b[2]}' comes after '{a[2]}' (L{a[1]}) "
                    f"— out of date order [table header L{hline}: {' | '.join(header)[:70]}]"
                )
    if not quiet:
        if not violations:
            print(f"OK  {path}  ({n_cal} calendar table(s), all chronological)")
        else:
            print(f"BAD {path}  ({n_cal} calendar table(s), {len(violations)} out of order):")
            for v in violations:
                print(v)
    return violations


def main(argv: list[str]) -> int:
    paths = [Path(a) for a in argv]
    if not paths:
        print("usage: check_calendar_sort.py <digest.md> [...]", file=sys.stderr)
        return 2
    bad = 0
    for p in paths:
        if not p.exists():
            print(f"BAD {p}  (file not found)")
            bad += 1
            continue
        bad += 1 if check_file(p) else 0
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
