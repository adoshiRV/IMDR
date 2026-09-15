"""Event-date check for Spider digests (daily + weekly).

Answers one question mechanically, so no edition has to trust a feed's own
day-bucketing: **for every calendar event the digest could quote, is the date
it carries the date the release actually happens in its OWN country?**

This exists because of a real failure. The 07 Sep 2026 weekly printed *"Japan
Q2 GDP, final | 07 Sep"*. The release is at 08:50 JST on **8 September**. Both
calendar lanes stored the correct instant — ``event_datetime =
2026-09-07 23:50+00:00`` — and disagreed only on the derived ``event_date``:
TradingEconomics said 07 Sep, Bloomberg BQL said 08 Sep. The digest read the
TE lane and published the wrong day, then listed the same release a second
time on 08 Sep from the BQL lane, as though they were two events.

The cause is structural, not a one-off. The TE calendar page groups rows by
**GMT calendar day**, and ``te_scraper.parse_calendar_html`` stores that page
date verbatim. So ``event_date`` on the TE lane is a UTC-day bucket, not a
release date, and it is off by one for every Asian release before 08:00 UTC.
``te_scraper._parse_time`` says as much -- *"consumers can shift by
event_date_offset if needed"* -- but no ``event_date_offset`` exists anywhere
in the repo, so no consumer ever shifted. The BQL lane mostly stores a local
date and is therefore right for Japan, but it is NOT a trustworthy arbiter
either: it files Colombian 18:00 COT and US 13:00 ET releases a day late.

Neither lane can referee the other. The only ground truth is the instant plus
the country's own timezone, which is what this script computes:

    expected_local_date = event_datetime  ->  dim_country.timezone

Three checks, all keyed off that one derivation:

  A. **Misdated rows.** Stored ``event_date`` != the date the release falls on
     in its own country. This alone would have caught the Japan error.
  B. **Split releases.** One instant + one country carrying two different
     ``event_date`` values across vendor lanes -- the shape that puts the same
     release in a digest twice, on two days.
  C. **Digest cross-check** (only when digest MDs are passed). Every date in a
     calendar table is matched back to its event and compared against the
     tz-correct date, so a wrong day is caught in the document itself and not
     merely in the table it came from.

Usage::

    # A + B over the edition's window (the pre-lock gate)
    python scripts/research/check_event_dates.py --as-of 2026-09-07

    # A + B + C: also verify the dates printed in the digest
    python scripts/research/check_event_dates.py --as-of 2026-09-07 \
        data/research_summary/weekly/2026/09/07/spider-weekly-digest.md

    python scripts/research/check_event_dates.py --window 2026-09-07:2026-09-18
    python scripts/research/check_event_dates.py --as-of 2026-09-07 --country JP

Exit code, by mode:

  * **With a digest** the question is *is this edition safe to lock?*, so the
    digest decides: exit 1 on any wrong date in the MD (C), 0 otherwise.
    A and B still print, as advisories — they are ingest defects that no edit
    to the MD can fix, and gating an edition on them would leave this check
    permanently red until the ingest is fixed, which is how a gate stops being
    read. ``--audit-strict`` makes them block anyway.
  * **With no digest** this *is* the ingest audit, so A and B decide.

``--strict`` additionally fails when a digest date could not be matched to any
event, i.e. when the check could not prove the date right.

Run it before locking a digest MD -- see spider.md.
"""
from __future__ import annotations

import argparse
import datetime as dt
import importlib.util
import re
import sys
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

# Reuse the digest table/date parsing rather than restating it. The sort check
# and this one must agree on what counts as a calendar table, or a table could
# pass one gate by being invisible to the other.
_SORT_PATH = Path(__file__).resolve().with_name("check_calendar_sort.py")
_spec = importlib.util.spec_from_file_location("check_calendar_sort", _SORT_PATH)
_ccs = importlib.util.module_from_spec(_spec)
sys.modules.setdefault("check_calendar_sort", _ccs)
_spec.loader.exec_module(_ccs)

_tables = _ccs._tables
_date_key = _ccs._date_key
_DATE_HEADERS = _ccs._DATE_HEADERS
_NON_CAL_FIRST_COL = _ccs._NON_CAL_FIRST_COL


# ---------------------------------------------------------------------------
# Timezone resolution
#
# dim_country.timezone covers every sovereign country that carries events.
# The gaps are the pseudo-countries plus Russia. A release attributed to the
# Eurozone is published by Eurostat/ECB on Brussels time; "Worldwide" has no
# single local calendar and is skipped rather than guessed.
# ---------------------------------------------------------------------------

TZ_OVERRIDES = {
    "EU": "Europe/Brussels",
    "RU": "Europe/Moscow",
}
TZ_SKIP = {"WW", "XX"}


def resolve_tz(country_code: str, tz_from_db: str | None) -> str | None:
    """IANA zone for a country, or None when it has no meaningful local date."""
    if country_code in TZ_SKIP:
        return None
    return tz_from_db or TZ_OVERRIDES.get(country_code)


def as_datetime(value) -> dt.datetime | None:
    """Coerce a DB `datetimeoffset` to an aware datetime.

    The legacy ODBC "SQL Server" driver this project pins hands back
    ``datetimeoffset`` as a *string* ('2026-09-07 23:50:00.0000000 +00:00'),
    not a datetime. Parsing it here keeps every caller working on real
    instants — reading a tz off a string is exactly the class of bug this
    script exists to catch.
    """
    if value is None or isinstance(value, dt.datetime):
        return value
    s = str(value).strip()
    if not s:
        return None
    # fromisoformat wants 'T', <=6 fractional digits, and no space before the
    # offset; SQL Server gives ' ', 7 digits, and ' +00:00'.
    s = re.sub(r"(\.\d{6})\d+", r"\1", s.replace(" ", "T", 1)).replace(" ", "")
    try:
        parsed = dt.datetime.fromisoformat(s)
    except ValueError:
        return None
    return parsed.replace(tzinfo=dt.timezone.utc) if parsed.tzinfo is None else parsed


def as_date(value) -> dt.date | None:
    """Coerce a DB `date` to a date (same driver caveat as `as_datetime`)."""
    if value is None or isinstance(value, dt.date) and not isinstance(value, dt.datetime):
        return value
    if isinstance(value, dt.datetime):
        return value.date()
    try:
        return dt.date.fromisoformat(str(value).strip()[:10])
    except ValueError:
        return None


def local_date(event_datetime: dt.datetime, tzname: str) -> dt.date:
    """The date an instant falls on in `tzname`. DST-correct via zoneinfo."""
    return event_datetime.astimezone(ZoneInfo(tzname)).date()


def classify_row(stored_date, event_datetime, country_code, tz_from_db):
    """Return (status, expected_date, tzname).

    status is OK, MISDATED, or SKIP (no instant, or no resolvable timezone --
    an estimated/placeholder row with a null datetime can't be checked and is
    not a failure).
    """
    event_datetime = as_datetime(event_datetime)
    stored_date = as_date(stored_date)
    if event_datetime is None:
        return "SKIP", None, None
    tzname = resolve_tz(country_code, tz_from_db)
    if not tzname:
        return "SKIP", None, None
    try:
        expected = local_date(event_datetime, tzname)
    except (ZoneInfoNotFoundError, ValueError):
        return "SKIP", None, None
    return ("OK" if stored_date == expected else "MISDATED"), expected, tzname


# ---------------------------------------------------------------------------
# Digest parsing
# ---------------------------------------------------------------------------

_COUNTRY_ALIASES = {
    "south korea": "KR", "korea": "KR", "japan": "JP", "china": "CN",
    "india": "IN", "taiwan": "TW", "hong kong": "HK", "singapore": "SG",
    "thailand": "TH", "indonesia": "ID", "malaysia": "MY",
    "philippines": "PH", "australia": "AU", "new zealand": "NZ",
    "united states": "US", "us": "US", "u.s.": "US", "usa": "US",
    "eurozone": "EU", "euro area": "EU", "europe": "EU",
    "united kingdom": "UK", "uk": "UK", "britain": "UK",
    "canada": "CA", "germany": "DE", "france": "FR", "italy": "IT",
    "spain": "ES", "switzerland": "CH", "norway": "NO", "sweden": "SE",
    "brazil": "BR", "mexico": "MX", "colombia": "CO", "chile": "CL",
    "south africa": "ZA", "turkey": "TR", "israel": "IL", "vietnam": "VN",
    # Central banks. A calendar row names the bank, not the country -- "ECB's
    # Lagarde speaks in Dublin" resolved to nothing and inherited whatever
    # section it sat under. Acronyms only where they are unambiguous at a word
    # boundary: no bare "BoC" (Bank of Canada vs Bank of China), no "BoT",
    # "BI" or "BoI" (ordinary words / two-letter collisions) -- those carry
    # their full names instead.
    # (playground/research/ingest/classifiers/bofa.py holds a parallel anchor
    # table; it matches report series+titles, not calendar cells, and sits on
    # the playground side of the tree. Deliberately not shared.)
    "ecb": "EU", "european central bank": "EU",
    "fomc": "US", "fed": "US", "federal reserve": "US",
    "boj": "JP", "bank of japan": "JP",
    "boe": "UK", "bank of england": "UK",
    "pboc": "CN", "people's bank of china": "CN",
    "rba": "AU", "reserve bank of australia": "AU",
    "rbnz": "NZ", "reserve bank of new zealand": "NZ",
    "bok": "KR", "bank of korea": "KR",
    "rbi": "IN", "reserve bank of india": "IN",
    "hkma": "HK", "mas": "SG", "monetary authority of singapore": "SG",
    "bsp": "PH", "bangko sentral": "PH",
    "bnm": "MY", "bank negara": "MY",
    "cbc": "TW", "bank of thailand": "TH", "bank indonesia": "ID",
    "bank of canada": "CA", "snb": "CH", "swiss national bank": "CH",
    "riksbank": "SE", "norges": "NO",
}

_COUNTRY_HEADERS = {"country", "market", "economy"}
# tokens that carry no matching signal
_STOP = {
    "the", "a", "an", "of", "and", "for", "to", "in", "on", "final", "prelim",
    "preliminary", "revised", "rate", "index", "data", "release", "report",
    "yoy", "mom", "qoq", "y/y", "m/m", "q/q", "sa", "nsa", "%",
}


def _norm_tokens(text: str) -> set[str]:
    """Lowercase alphanumeric tokens, minus noise words."""
    toks = re.findall(r"[a-z0-9]+", text.lower())
    return {t for t in toks if t not in _STOP and len(t) > 1}


def _country_from_text(text: str) -> str | None:
    """Country named in `text`, or None.

    Picks the EARLIEST-mentioned country, not the first alias in registry
    order: a "China August trade" row whose house-calls cell also mentions
    Korea names China, and order-of-registry matching would call it Korea.
    Longer aliases win at equal position so "south korea" beats "korea".
    """
    low = text.lower().strip().strip("*_# ")
    if low in _COUNTRY_ALIASES:
        return _COUNTRY_ALIASES[low]
    best = None
    for name, cc in _COUNTRY_ALIASES.items():
        m = re.search(rf"\b{re.escape(name)}\b", low)
        if m and (best is None or (m.start(), -len(name)) < best[0]):
            best = ((m.start(), -len(name)), cc)
    return best[1] if best else None


#  A cell holding only a clock time, optionally with a zone or a range:
#  "09:30", "14:00 SGT", "08:30 ET", "13:15-13:45", "21:50 JST (prev day)".
_TIME_ONLY_RE = re.compile(
    r"^[\s(\[]*\d{1,2}[:.]\d{2}"
    r"(\s*[-–—]\s*\d{1,2}[:.]\d{2})?"
    r"(\s*[ap]\.?m\.?)?"
    r"(\s*[A-Za-z/+\-0-9]{1,12})?"
    r"[\s)\]]*$",
    re.IGNORECASE,
)
#  Cells that carry no country signal and must not stand in for the event text.
_EMPTY_CELL_RE = re.compile(r"^[\s\-–—.*_|:]*$")


def _is_signal_cell(text: str) -> bool:
    """True when a cell could plausibly name a country.

    A time-of-day or a dash placeholder never can. Treating one as the row's
    lead is what made a ``Date | Time | Event`` board resolve to nothing and
    fall through to the enclosing section heading, stamping every row with
    the section's country (a CN heading over a board of US/JP/EU releases).
    """
    if _EMPTY_CELL_RE.match(text):
        return False
    return not _TIME_ONLY_RE.match(text.strip())


def _row_lead(cells: list[str], date_col: int, country_col: int | None) -> str:
    """The row's first cell that could name a country, or ''.

    Skips the date and country columns (handled by the caller) and any cell
    carrying no country signal, so column ORDER inside a calendar table stops
    changing which country the row resolves to.
    """
    return next(
        (
            c for k, c in enumerate(cells)
            if k != date_col and k != country_col and _is_signal_cell(c)
        ),
        "",
    )


def _resolve_year(month: int, day: int, as_of: dt.date) -> dt.date:
    """Pick the year that puts (month, day) nearest the edition date.

    A digest compiled on 31 Dec legitimately carries early-January dates, so
    the year is chosen by proximity rather than assumed to be the edition's.
    """
    best = None
    for yr in (as_of.year - 1, as_of.year, as_of.year + 1):
        try:
            cand = dt.date(yr, month, day)
        except ValueError:
            continue
        if best is None or abs((cand - as_of).days) < abs((best - as_of).days):
            best = cand
    return best


def digest_event_rows(path: Path, as_of: dt.date):
    """Yield (line_no, date, country_code|None, event_text, raw_date_cell).

    One entry per calendar-table row whose date cell parses to a real day.
    Country comes from a Country/Market column when the table has one, else
    from the nearest preceding heading naming a country.
    """
    lines = path.read_text(encoding="utf-8").split("\n")

    # heading line no -> country, for section-scoped per-country boards
    heading_cc: list[tuple[int, str]] = []
    for i, line in enumerate(lines):
        if line.lstrip().startswith("#"):
            cc = _country_from_text(line)
            if cc:
                heading_cc.append((i + 1, cc))

    def _section_country(lno: int) -> str | None:
        cc = None
        for hl, c in heading_cc:
            if hl <= lno:
                cc = c
            else:
                break
        return cc

    for hline, header, data in _tables(lines):
        date_col = next(
            (k for k, h in enumerate(header)
             if h.lower().strip("* ") in _DATE_HEADERS),
            None,
        )
        if date_col is None:
            continue
        if header and header[0].lower().strip("* ") in _NON_CAL_FIRST_COL:
            continue
        country_col = next(
            (k for k, h in enumerate(header)
             if h.lower().strip("* ") in _COUNTRY_HEADERS),
            None,
        )
        # A table whose rows name their own countries is a multi-country grid
        # (the Tier-1 "this week"/"week ahead" boards). The enclosing section
        # heading must NOT be applied to its unlabelled rows: an "ECB decision"
        # row sitting inside a US section would be checked as a US release and
        # bind to whatever US event shares two tokens with it.
        multi_country = country_col is not None or sum(
            1 for _, cells in data
            if _country_from_text(_row_lead(cells, date_col, country_col))
        ) >= 2

        for lno, cells in data:
            if date_col >= len(cells):
                continue
            key = _date_key(cells[date_col])
            if key is None or key[0] == 0 or key[1] == 0:
                continue  # soft, time-only, or month-only cell
            when = _resolve_year(key[0], key[1], as_of)
            others = " ".join(
                c for k, c in enumerate(cells) if k not in (date_col, country_col)
            )
            # Country column first; then a country named in the row itself
            # (the Tier-1 "this week" grids are multi-country with no Country
            # column, so the section heading would mislabel every row); then
            # the enclosing section, for per-country boards.
            cc = None
            if country_col is not None and country_col < len(cells):
                cc = _country_from_text(cells[country_col])
            if cc is None:
                # The event/theme cell names the country in the multi-country
                # Tier-1 grids ("Japan Q2 GDP, final"). Read it before the
                # section heading, which would stamp every row with the
                # enclosing country.
                cc = _country_from_text(_row_lead(cells, date_col, country_col))
            if cc is None and not multi_country:
                cc = _section_country(lno)
            yield lno, when, cc, others, cells[date_col]


def match_event(when, cc, text, events, window_days=3):
    """Best DB event for a digest row, or None.

    Candidates are same-country events whose tz-correct date is within
    `window_days` of the digest's date; the winner is the one sharing the most
    name tokens. Requires >= 2 shared tokens so that a generic row ("GDP") does
    not bind to an unrelated release and manufacture a violation.

    Ties break toward the candidate NEAREST the printed date. Recurring events
    (an ECB speech, a bill auction) appear several times in a window with
    identical names, so a tie broken arbitrarily would report the digest as
    wrong for having picked a different instance of the same thing.
    """
    want = _norm_tokens(text)
    if not want:
        return None
    best, best_key = None, (1, 0)
    for ev in events:
        if ev["country_code"] != cc or ev["expected"] is None:
            continue
        distance = abs((ev["expected"] - when).days)
        if distance > window_days:
            continue
        key = (len(want & _norm_tokens(ev["event_name"])), -distance)
        if key > best_key:
            best, best_key = ev, key
    return best if best_key[0] >= 2 else None


# ---------------------------------------------------------------------------
# DB probe
# ---------------------------------------------------------------------------

_SQL = """
SELECT e.id, e.event_date, e.event_datetime, e.event_name, e.vendor_id,
       e.is_estimated, c.country_code, c.timezone
FROM calendar.cb_events e
JOIN dbo.dim_country c ON c.id = e.country_id
WHERE e.event_date >= :start AND e.event_date <= :end
"""


def probe(conn, start: dt.date, end: dt.date, countries: list[str] | None):
    from sqlalchemy import text as _sql_text

    sql = _SQL
    params = {"start": start.isoformat(), "end": end.isoformat()}
    if countries:
        marks = ", ".join(f":c{i}" for i in range(len(countries)))
        sql += f" AND c.country_code IN ({marks})"
        params.update({f"c{i}": cc for i, cc in enumerate(countries)})
    rows = []
    for r in conn.execute(_sql_text(sql), params):
        status, expected, tzname = classify_row(
            r.event_date, r.event_datetime, r.country_code, r.timezone
        )
        rows.append({
            "id": r.id, "stored": as_date(r.event_date),
            "instant": as_datetime(r.event_datetime),
            "event_name": r.event_name, "vendor_id": r.vendor_id,
            "is_estimated": bool(r.is_estimated),
            "country_code": r.country_code, "tz": tzname,
            "status": status, "expected": expected,
        })
    return rows


_LANE = {73: "tradingeconomics", 4: "bloomberg_bql"}


def _lane(vendor_id) -> str:
    return _LANE.get(vendor_id, f"vendor:{vendor_id}")


def find_split_releases(rows):
    """One country + one instant carrying two different stored event_dates."""
    by_instant: dict[tuple, list] = {}
    for r in rows:
        if r["instant"] is None:
            continue
        by_instant.setdefault((r["country_code"], r["instant"]), []).append(r)
    splits = []
    for (cc, instant), group in by_instant.items():
        dates = {r["stored"] for r in group}
        if len(dates) > 1:
            splits.append((cc, instant, group))
    return sorted(splits, key=lambda s: (s[1], s[0]))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("digests", nargs="*",
                    help="digest MD path(s) to cross-check (optional)")
    ap.add_argument("--as-of", default=None,
                    help="edition date (default: today). Window defaults to "
                         "as-of-7d .. as-of+21d, covering both look-back and "
                         "week-ahead buckets.")
    ap.add_argument("--window", default=None,
                    help="explicit START:END window, overrides --as-of span")
    ap.add_argument("--country", action="append", default=None,
                    help="restrict to ISO country code(s), e.g. --country JP")
    ap.add_argument("--strict", action="store_true",
                    help="also fail when a digest date cannot be matched to "
                         "an event (unproven, not merely unflagged)")
    ap.add_argument("--audit-strict", action="store_true",
                    help="fail on upstream misdated lane rows (A) and split "
                         "releases (B) even when checking a digest. Off by "
                         "default: those are ingest defects no MD edit can "
                         "fix, and gating on them keeps the check red for "
                         "every edition until the ingest is fixed.")
    args = ap.parse_args(argv)

    try:
        as_of = (dt.date.fromisoformat(args.as_of) if args.as_of
                 else dt.date.today())
    except ValueError:
        print(f"bad --as-of: {args.as_of!r}", file=sys.stderr)
        return 1
    if args.window:
        try:
            s, e = args.window.split(":", 1)
            start, end = dt.date.fromisoformat(s), dt.date.fromisoformat(e)
        except ValueError:
            print(f"bad --window: {args.window!r} (want START:END)",
                  file=sys.stderr)
            return 1
    else:
        start, end = as_of - dt.timedelta(days=7), as_of + dt.timedelta(days=21)

    paths = [Path(p) for p in args.digests]
    missing = [p for p in paths if not p.exists()]
    if missing:
        for p in missing:
            print(f"BAD {p}  (file not found)")
        return 1

    # Imported here so --help works without DB settings present.
    from imdr.config.settings import get_settings
    from imdr.connectors.mssql import MSSQLConnector

    connector = MSSQLConnector(get_settings())
    try:
        with connector.read_engine.connect() as conn:
            rows = probe(conn, start, end, args.country)
    finally:
        connector.dispose()

    print(f"Event dates {start} .. {end} "
          f"(edition {as_of}) — stored date vs the country's own calendar\n")

    checked = [r for r in rows if r["status"] != "SKIP"]
    misdated = [r for r in rows if r["status"] == "MISDATED"]
    skipped = len(rows) - len(checked)

    # -- A. misdated rows ---------------------------------------------------
    by_lane: dict[str, list] = {}
    for r in rows:
        by_lane.setdefault(_lane(r["vendor_id"]), []).append(r)
    header = f"{'lane':<20} {'rows':>6} {'checked':>8} {'misdated':>9}  status"
    print(header)
    print("-" * len(header))
    for lane in sorted(by_lane):
        grp = by_lane[lane]
        ck = [r for r in grp if r["status"] != "SKIP"]
        bad = [r for r in grp if r["status"] == "MISDATED"]
        print(f"{lane:<20} {len(grp):>6} {len(ck):>8} {len(bad):>9}  "
              f"{'OK' if not bad else 'MISDATED'}")
    if skipped:
        print(f"\n{skipped} row(s) skipped (no instant, or no local calendar) "
              f"— placeholder/estimated rows are not failures.")

    if misdated:
        # Per-country breakdown first: the detail list is capped, and a
        # truncated list hides whether a country is wholly or partly affected.
        print(f"\n!! A. {len(misdated)} row(s) dated to the wrong day in their "
              f"own country. By country:")
        per: dict[tuple[str, str], list] = {}
        for r in misdated:
            per.setdefault((r["country_code"], _lane(r["vendor_id"])), []).append(r)
        tot = {}
        for r in checked:
            tot[(r["country_code"], _lane(r["vendor_id"]))] = \
                tot.get((r["country_code"], _lane(r["vendor_id"])), 0) + 1
        sub = f"   {'country':<8} {'lane':<18} {'misdated':>9} {'of':>6}"
        print(sub)
        print("   " + "-" * (len(sub) - 3))
        for (cc, lane), grp in sorted(per.items(), key=lambda kv: -len(kv[1])):
            print(f"   {cc:<8} {lane:<18} {len(grp):>9} {tot.get((cc, lane), 0):>6}")
        print(f"\n   Detail:")
        for r in sorted(misdated, key=lambda r: (r["instant"], r["country_code"]))[:40]:
            print(f"   [{_lane(r['vendor_id'])}] {r['country_code']} "
                  f"id={r['id']}  stored {r['stored']} but "
                  f"{r['instant']:%Y-%m-%d %H:%M}Z is {r['expected']} "
                  f"in {r['tz']}  — {r['event_name'][:60]}")
        if len(misdated) > 40:
            print(f"   ... and {len(misdated) - 40} more")

    # -- B. split releases --------------------------------------------------
    splits = find_split_releases(rows)
    if splits:
        print(f"\n!! B. {len(splits)} release(s) carrying two different dates "
              f"across lanes — a digest can print these twice:")
        for cc, instant, group in splits[:20]:
            variants = ", ".join(
                f"{_lane(r['vendor_id'])}={r['stored']}"
                for r in sorted(group, key=lambda r: r["stored"])
            )
            correct = next((r["expected"] for r in group if r["expected"]), None)
            print(f"   {cc} {instant:%Y-%m-%d %H:%M}Z  {variants}  "
                  f"-> correct local date {correct}")
        if len(splits) > 20:
            print(f"   ... and {len(splits) - 20} more")

    # -- C. digest cross-check ---------------------------------------------
    md_violations, md_unmatched = [], []
    for p in paths:
        n_rows = n_ok = 0
        for lno, when, cc, text, raw in digest_event_rows(p, as_of):
            n_rows += 1
            if cc is None:
                md_unmatched.append((p, lno, raw, text, "no country"))
                continue
            ev = match_event(when, cc, text, rows)
            if ev is None:
                md_unmatched.append((p, lno, raw, text, f"no {cc} event match"))
                continue
            if ev["expected"] != when:
                md_violations.append((p, lno, raw, when, ev))
            else:
                n_ok += 1
        print(f"\n{p.name}: {n_rows} dated calendar row(s), {n_ok} verified "
              f"against the country's own calendar")

    if md_violations:
        print(f"\n!! C. {len(md_violations)} digest date(s) on the wrong day:")
        for p, lno, raw, when, ev in md_violations:
            print(f"   {p.name}:{lno}  printed '{raw}' ({when}) but "
                  f"{ev['country_code']} {ev['event_name'][:44]} releases "
                  f"{ev['expected']} ({ev['instant']:%H:%M}Z, {ev['tz']})")
    if md_unmatched:
        lead = "!!" if args.strict else "--"
        print(f"\n{lead} {len(md_unmatched)} digest date(s) could not be matched "
              f"to an event{' (strict: counted as failures)' if args.strict else ' (not proven right or wrong)'}:")
        for p, lno, raw, text, why in md_unmatched[:20]:
            print(f"   {p.name}:{lno}  '{raw}'  {why}  — {text[:56]}")
        if len(md_unmatched) > 20:
            print(f"   ... and {len(md_unmatched) - 20} more")

    # Exit semantics. With a digest to check, the question is "is THIS edition
    # safe to lock?", so the digest decides (C, plus unmatched under --strict)
    # and the upstream lane defects (A/B) are reported as advisories. They are
    # a property of the ingest, not of the edition, and cannot be fixed by
    # editing the MD — gating on them would leave the check permanently red
    # until the ingest is fixed, which is how a gate gets ignored.
    # With no digest, this IS the ingest audit, so A/B decide.
    # --audit-strict forces A/B to block in either mode.
    upstream = bool(misdated or splits)
    digest_bad = bool(md_violations or (args.strict and md_unmatched))
    failed = digest_bad or (upstream and (args.audit_strict or not paths))

    print()
    if upstream and paths and not args.audit_strict:
        print(f"NOTE: {len(misdated)} misdated lane row(s) and {len(splits)} "
              f"split release(s) upstream (A/B above). Not blocking this "
              f"edition — no MD edit can fix them — but every date the digest "
              f"takes from those lanes must come from this check, not from "
              f"`event_date`. Pass --audit-strict to gate on them.")
    if not failed:
        if paths:
            print("Every date in the digest agrees with its own country's "
                  "calendar. Safe to lock.")
        else:
            print("All event dates agree with their own country's calendar — "
                  "quote these dates, and never take a lane's event_date as a "
                  "release date without this check.")
        return 0
    if digest_bad:
        print("Event-date check FAILED — do not lock the edition. A lane's "
              "event_date is a day-bucket, not a release date; the instant "
              "plus dim_country.timezone is the only ground truth.")
    else:
        print("Event-date audit FAILED — the calendar lanes carry dates that "
              "do not match the release country's own calendar.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
