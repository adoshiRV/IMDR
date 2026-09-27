"""RBI Sectoral Deployment of Bank Credit — monthly outstanding by sector.

Closes the data half of **DG24** (India sectoral bank credit & deposits):
IMDR held no India credit series of any kind, against a dashboard
`credit_aggregates` category that already carried AU 33 / KR 3 / IN 0.

Source: the monthly RBI press release "Sectoral Deployment of Bank
Credit", indexed at `Data_Sectoral_Deployment.aspx`. Each release ships
one XLSX with two statements:

  Statement 1  Deployment of Gross Bank Credit by Major Sectors
               bank / food / non-food credit, agriculture, industry
               (micro-small / medium / large), services (incl. NBFCs,
               HFCs, trade, commercial real estate), personal loans
               (housing, vehicle, gold, credit card, education,
               consumer durables), and the priority-sector memo block
  Statement 2  Industry-wise Deployment of Gross Bank Credit
               19 industries + sub-industries (petroleum & coal,
               edible oils, all engineering, gems & jewellery, ...)

**82 series x 90 monthly prints, Jan-2019 -> Jul-2026, gapless** (7,380
observations), in Rs. crore outstanding. Growth rates are NOT ingested --
the release carries YoY and FY variation columns and we drop them; a %
change is the consumer's kernel, not a stored series.

**Access is two-stage.** The index and each press-release page are plain
HTTP (the year switch is an ASP.NET postback on a hidden `hdnYear`
field), so release discovery costs no browser. Only the XLSX itself sits
on `rbidocs.rbi.org.in` behind Akamai TSPD and needs HEADED Chrome --
see `imdr.domains.econ.rbi_tspd`. Downloads are cached on disk, so a
backfill is paid once and the monthly tick costs one file.

**History floor.** XLSX attachments start with the June-2019 release
(verified across all 189 releases back to 2011 on 2026-09-15); everything
earlier is PDF-only. Of the 85 downloadable files, **20 are declined** by
the two gates in `parse_statement` -- two are Rs. billion, and eighteen
(Aug-2019 -> Dec-2020) are Rs. crore but carry a different *taxonomy*,
not merely a different shape. Nothing is lost at the start of the record:
the first current-layout release (Jan-2021) carries `18.Jan,2019` as its
oldest column, so the back-references reach the Jan-2019 SIBC recast --
which is where DBIE says the current series begins. 90 gapless months
from 65 usable releases, >3x DG24's stated floor of 25 monthly
observations for a 2-year CAGR.

**Two breaks a consumer must know about**, both recorded here rather
than silently smoothed:

  1. Effective 31 December 2025 the "last reporting fortnight" became
     the last DAY of the month (Banking Laws (Amendment) Act 2025). YoY
     from Dec-2025 on compares month-end against the old-definition
     fortnight of the year-ago month.
  2. The sectoral release covers ~41 select SCBs (~95% of non-food
     credit), NOT all scheduled commercial banks. It is a different
     universe from the Section-42 aggregate, and the two must never
     share an as-of stamp.

**Five columns per release, and which one wins a month.** Each release
carries five "Outstanding as on" columns: the reported month, the two
year-ago anchors its YoY columns use, and two financial-year anchors. All
five are read -- that is what makes the record gapless from Jan-2019
despite the first current-layout release being Jan-2021 -- and a month is
resolved by, in order:

  1. the **latest reported date inside that calendar month**, then
  2. the **latest release** to print that date.

Rule 1 stops an FY anchor from displacing a genuine month-end: the
FY2024-25 anchor prints as `4.Apr,2025`, while the April-2025 release
itself reports `18.Apr,2025`, so April keeps the month-end figure.
Rule 2 makes a restatement win: RBI revises, and its own published YoY
compares the current print against the year-ago figure **as restated in
the current release**. Storing first prints instead reproduces
Agriculture's 17.0% but misses Services (21.2% against a published
22.9%), because the July-2025 Services level was revised from 5,113,966
down to 5,040,440 a year later. Both behaviours are pinned by tests.

Run (monthly tick -- latest 3 releases, load to DB):
    python -m scripts.econ.in.rbi.rbi_sectoral_credit

Run (full backfill of the Rs.-crore era, no DB write):
    python -m scripts.econ.in.rbi.rbi_sectoral_credit --since 2019-01-01 --no-load
"""
from __future__ import annotations

import datetime
import re
import sys
from pathlib import Path

import httpx
import openpyxl

from imdr.domains.econ.rbi_parse import MONTHS as _MONTHS
from imdr.domains.econ.rbi_parse import parse_date as _parse_date
from imdr.domains.econ.rbi_parse import parse_number as _num
from imdr.domains.econ.rbi_tspd import download_all
from imdr.domains.econ.schema import IndicatorRow, ObservationRow
from scripts.econ._runner import run_main

UTC = datetime.timezone.utc

# parents[0]=rbi, [1]=in, [2]=econ, [3]=scripts, [4]=repo root
_REPO_ROOT = Path(__file__).resolve().parents[4]
# Its OWN profile dir. Sharing one with another RBI fetcher deadlocks the
# second caller on Chrome's exclusive user-data-dir lock.
PROFILE = _REPO_ROOT / "data" / "econ" / "in" / "rbi" / "_profile_sibc"
DL_DIR = _REPO_ROOT / "data" / "econ" / "in" / "rbi" / "_downloads_sibc"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36")
INDEX_URL = "https://rbi.org.in/Scripts/Data_Sectoral_Deployment.aspx"
PR_URL = "https://rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx?prid={prid}"

PREFIX = "INDIA.SECTORAL_CREDIT"
VENDOR = "RBI"
# Releases to pull when no --since is given (a monthly tick; >1 so a
# late-published month is still picked up).
DEFAULT_RELEASES = 3
# Earliest year worth indexing -- the first XLSX attachment is June 2019.
FIRST_XLSX_YEAR = 2019

# Release rows on the index page: `prid=63478>Sectoral Deployment of Bank
# Credit <dash> July 2026`. The dash is a cp1252 en-dash served as a stray
# byte, so match any single character.
_REL_RE = re.compile(
    r"prid=(\d+)>Sectoral Deployment of Bank Credit\s*.\s*([A-Za-z]+)\s+(\d{4})")
_XLSX_RE = re.compile(r'href="(https://rbidocs\.rbi\.org\.in/[^"]+\.xlsx)"', re.I)

# Labels whose generated slug would drift between eras or run absurdly
# long. Keyed on the slug the generic slugger produces.
_SLUG_ALIASES = {
    # RBI renamed "Gross Bank Credit" -> "Bank Credit" during the era;
    # same series (= food + non-food), so one code.
    "GROSS_BANK_CREDIT": "BANK_CREDIT",
    "ADVANCES_TO_INDIVIDUALS_AGAINST_SHARE_BONDS_ETC": "ADVANCES_AGAINST_SHARES_BONDS",
    # "Advances against Fixed Deposits (Including FCNR (B), NRNR Deposits
    # etc.)" -- the NESTED parenthesis defeats the gloss-stripper, which
    # leaves the tail behind. Named rather than made the regex recursive.
    "ADVANCES_AGAINST_FIXED_DEPOSITS_NRNR_DEPOSITS_ETC": "ADVANCES_AGAINST_FIXED_DEPOSITS",
    "WEAKER_SECTIONS_INCLUDING_NET_PSLC_SF_MF": "WEAKER_SECTIONS",
    "BASIC_METAL_AND_METAL_PRODUCT": "BASIC_METAL_AND_METAL_PRODUCTS",
    "VEHICLES_VEHICLE_PARTS_AND_TRANSPORT_EQUIPMENT": "VEHICLES_AND_TRANSPORT_EQUIPMENT",
    "RUBBER_PLASTIC_AND_THEIR_PRODUCTS": "RUBBER_AND_PLASTIC_PRODUCTS",
}

# Rows that must not become a series under this prefix.
#
# `INDUSTRIES` is `Industries (2.1 to 2.19)`, Statement 2's total, which
# is byte-identical to Statement 1's `2. Industry`; emitting both would
# put two codes on one concept.
#
# `BANK_CREDIT` / `FOOD_CREDIT` / `NON_FOOD_CREDIT` are rows I, II and III
# of Statement 1, and they are a DIFFERENT UNIVERSE from the sector rows
# printed underneath them. RBI's own note (1) says so: those three come
# from the fortnightly **Section-42** return covering ALL scheduled
# commercial banks, while the sectoral rows come from the **SIBC** return
# covering ~41 select banks (~95% of non-food credit). Verified against
# DBIE reportId 1130 on 2026-09-15 -- Mar-2026 food credit ties to the
# crore (70,271) and bank credit differs only by revision vintage.
# Everything under `INDIA.SECTORAL_CREDIT.*` is therefore one universe,
# the SIBC one; the Section-42 aggregates are owned by
# `rbi_dbie_scb_business.py` as `INDIA.SCB_BUSINESS.*`, which holds them
# with deeper history and the right universe in its name. That is DG24's
# second trap ("bars sourced from the two cannot share an as-of stamp")
# made structural rather than left as a footnote.
_SKIP_SLUGS = {"INDUSTRIES", "INDUSTRY_TOTAL",
               "BANK_CREDIT", "FOOD_CREDIT", "NON_FOOD_CREDIT"}

# Labels that only mean something under their parent. Statement 2 carries
# three separate `Others` rows -- 2.2.4 under Food Processing, 2.9.4 under
# Chemicals, 2.14.2 under All Engineering -- and an unqualified slug would
# silently merge all three into one series.
#
# KNOWN LIMIT, accepted: qualification only fires for a SUB-row (a section
# number containing a dot). A bare top-level `Others` would slug to plain
# `OTHERS` and be emitted unqualified. No such row exists in the 65-release
# archive as of 2026-09-15, and if one appeared alongside a second the
# collision guard below would still catch it -- but a lone one would pass
# through under a vague code. Qualify it here if RBI ever adds one.
_GENERIC_SLUGS = {"OTHERS", "OTHER"}


# ---------------------------------------------------------------------------
# Release discovery -- plain HTTP, no browser
# ---------------------------------------------------------------------------

def _hidden(html: str, name: str) -> str:
    m = re.search(r'name="%s"[^>]*value="([^"]*)"' % re.escape(name), html)
    return m.group(1) if m else ""


def list_releases(since: datetime.date | None) -> list[dict]:
    """Every release from `since` (or the last DEFAULT_RELEASES), newest first.

    Switching year on the index is an ASP.NET postback; the landing page
    already carries the current year, so only earlier years cost a POST.
    """
    this_year = datetime.date.today().year
    if since is None:
        years = [this_year, this_year - 1]
    else:
        years = list(range(this_year, max(since.year, FIRST_XLSX_YEAR) - 1, -1))

    out: list[dict] = []
    seen: set[str] = set()
    with httpx.Client(headers={"User-Agent": UA}, timeout=40,
                      follow_redirects=True) as c:
        landing = c.get(INDEX_URL).text
        for y in years:
            page = landing if y == this_year else c.post(INDEX_URL, data={
                "__VIEWSTATE": _hidden(landing, "__VIEWSTATE"),
                "__VIEWSTATEGENERATOR": _hidden(landing, "__VIEWSTATEGENERATOR"),
                "__EVENTVALIDATION": _hidden(landing, "__EVENTVALIDATION"),
                "hdnYear": str(y), "btn": "",
            }).text
            for prid, mon, yr in _REL_RE.findall(page):
                if prid in seen:
                    continue
                mi = _MONTHS.get(mon.lower())
                if mi is None:
                    continue
                seen.add(prid)
                out.append({
                    "prid": prid,
                    "label": f"{yr}_{mi:02d}",
                    "report_month": datetime.date(int(yr), mi, 1),
                })

    out.sort(key=lambda r: r["report_month"], reverse=True)
    if since is not None:
        out = [r for r in out if r["report_month"] >= since.replace(day=1)]
    else:
        out = out[:DEFAULT_RELEASES]
    return out


def resolve_xlsx(releases: list[dict]) -> list[dict]:
    """Attach the XLSX url (and the release date encoded in its name)."""
    kept: list[dict] = []
    with httpx.Client(headers={"User-Agent": UA}, timeout=40,
                      follow_redirects=True) as c:
        for r in releases:
            try:
                m = _XLSX_RE.search(c.get(PR_URL.format(prid=r["prid"])).text)
            except Exception as e:
                print(f"  {r['label']}: press-release fetch failed "
                      f"({type(e).__name__}), skip")
                continue
            if not m:
                # Pre-June-2019 releases attach a PDF, not an XLSX.
                print(f"  {r['label']}: no XLSX attachment, skip")
                continue
            url = m.group(1)
            kept.append({**r, "xlsx": url,
                         "release_date": _release_date_from_name(url)})
    return kept


def _release_date_from_name(url: str) -> datetime.datetime | None:
    """RBI encodes the publication date as DDMMYYYY in the file name."""
    m = re.search(r"(\d{2})(\d{2})(20\d{2})", url.rsplit("/", 1)[-1])
    if not m:
        return None
    try:
        d = datetime.date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
    except ValueError:
        return None
    return datetime.datetime(d.year, d.month, d.day, tzinfo=UTC)


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def _slug(label: str) -> tuple[str, str]:
    """`'2.9.1. Fertiliser'` -> `('2.9.1', 'FERTILISER')`.

    Returns (section number, slug). The section number goes to
    `source_code` for traceability; the slug carries the concept, because
    RBI renumbers rows when it inserts one but renames them rarely.
    """
    s = re.sub(r"\s+", " ", str(label).replace("\n", " ")).strip()
    s = s.rstrip(" ,;")
    # trailing "of which," on the NBFC row
    s = re.sub(r"\s*of which[,:]?$", "", s, flags=re.I)

    section = ""
    m = re.match(r"^((?:[IVX]+|\d+(?:\.\d+)*))\s*[.)]\s*(.+)$", s)
    if m:
        section, s = m.group(1), m.group(2)
    else:
        m = re.match(r"^\((i{1,3}|iv|v|vi{1,3}|ix|x)\)\s*(.+)$", s, re.I)
        if m:
            section, s = m.group(1).lower(), m.group(2)

    # footnote superscript rendered as a trailing digit: "Wholesale Trade1"
    s = re.sub(r"(?<=[A-Za-z)\]])\d$", "", s).strip()
    # drop parentheticals -- every one in this release is a gloss
    s = re.sub(r"\([^)]*\)", " ", s)
    s = re.sub(r"[^A-Za-z0-9]+", "_", s).strip("_").upper()
    s = re.sub(r"_+", "_", s)
    return section, _SLUG_ALIASES.get(s, s)


def _sheet_rows(ws) -> list[list]:
    rows: list[list] = []
    for raw in ws.iter_rows(values_only=True):
        row = list(raw)
        while row and (row[-1] is None or str(row[-1]).strip() == ""):
            row.pop()
        rows.append(row)
    return rows


def _unit_line(rows: list[list]) -> str:
    """The `(Rs. ...)` line. Usually row 1, but not always.

    Two 2019 releases shift it to row 2, so scan rather than index -- an
    index miss would read as "unit unknown" and drop a whole release.
    """
    for row in rows[:6]:
        for cell in row or []:
            text = str(cell or "").strip()
            if text.lower().startswith("(rs"):
                return text
    return ""


def _has_sr_no_column(rows: list[list]) -> bool:
    """True for the pre-2021 two-column (`Sr.No` | `Sector`) layout."""
    for row in rows[:8]:
        for cell in (row or [])[:2]:
            if re.sub(r"[^a-z]", "", str(cell or "").lower()) == "srno":
                return True
    return False


def parse_statement(rows: list[list], statement: int) -> tuple[dict, list[tuple]]:
    """One sheet -> ({slug: (section, raw_label)}, [(slug, date, value)]).

    Returns ({}, []) for any sheet outside the current era. Two gates,
    both of which decline rather than guess:

    * **Unit.** The June and July 2019 releases are in **Rs. billion**.
      Reading them as crore would understate every value 100x.
    * **Layout.** Every release from Aug-2019 to Dec-2020 is in crore but
      splits the row label across a separate `Sr.No` column and a
      `Sector` column -- and, more importantly, carries a **different
      taxonomy**, not just a different shape: `Agriculture & Allied
      Activities` for `Agriculture and Allied Activities`, `Micro &
      Small` for `Micro and Small`, no `Aviation` and no `Loans against
      gold jewellery` row, a priority-sector block with `Micro-Credit`
      and `State-Sponsored Orgs. for SC/ST` that the current block does
      not have, and section numbers that mean different things either
      side of the break (`3.5` is Aviation now and Professional Services
      then). Splicing that onto the current codes would manufacture
      parallel half-series and fake level breaks, so the era is declined
      whole. Nothing is lost at the start of the record: the first
      current-layout release (Jan-2021) carries `18.Jan,2019` as its
      oldest column, so the back-references reach the Jan-2019 recast
      anyway.
    """
    unit_line = _unit_line(rows)
    if "crore" not in unit_line.lower():
        print(f"    statement {statement}: unit line {unit_line!r} is not "
              f"Rs. crore — Rs.-billion era, skipped")
        return {}, []
    if _has_sr_no_column(rows):
        print(f"    statement {statement}: pre-2021 Sr.No layout and "
              f"taxonomy, skipped")
        return {}, []

    labels: dict[str, tuple[str, str]] = {}
    obs: list[tuple] = []
    dates: list[tuple[int, datetime.date]] = []
    in_priority = False
    by_section: dict[str, str] = {}   # "2.2" -> "FOOD_PROCESSING"

    for row in rows:
        if not row:
            continue
        head = str(row[0]).strip() if row[0] is not None else ""

        if head.lower().startswith(("note", "source")):
            break

        # A header row: >= 3 of the value cells parse as dates.
        found = []
        for i, c in enumerate(row[1:], start=1):
            if c is None:
                continue
            d = _parse_date(str(c))
            if d is not None:
                found.append((i, d))
        if len(found) >= 3:
            dates = found
            continue

        if not head or not dates:
            continue

        section, slug = _slug(head)
        if not slug or slug in _SKIP_SLUGS:
            continue

        # The priority-sector memo block restates sectors already carried
        # above on a different definition; namespace it so
        # `PRIORITY_SECTOR_HOUSING` cannot collide with `HOUSING`.
        if slug.startswith("PRIORITY_SECTOR"):
            in_priority = True
            continue
        if in_priority:
            slug = f"PRIORITY_SECTOR_{slug}"
        elif slug in _GENERIC_SLUGS and "." in section:
            parent = by_section.get(section.rsplit(".", 1)[0])
            if parent:
                slug = f"{parent}_{slug}"
        if section:
            by_section[section] = slug

        vals = []
        for i, d in dates:
            v = _num(row[i]) if i < len(row) else None
            if v is not None:
                vals.append((d, v))
        if not vals:
            continue

        prior = labels.get(slug)
        if prior is not None and prior[0] != section:
            # Two different RBI rows collapsing onto one code silently
            # merges two concepts into one series. Fail loudly instead --
            # the fix is an entry in `_SLUG_ALIASES` or `_GENERIC_SLUGS`.
            raise ValueError(
                f"slug collision in statement {statement}: {slug!r} claimed by "
                f"section {prior[0]!r} ({prior[1]!r}) and {section!r} ({head!r})"
            )
        labels.setdefault(slug, (section, re.sub(r"\s+", " ", head).strip()))
        for d, v in vals:
            obs.append((slug, d, v))

    return labels, obs


# ---------------------------------------------------------------------------
# Fetch
# ---------------------------------------------------------------------------

def resolve_months(
    candidates: list[tuple[str, datetime.date, datetime.date, float]],
) -> dict[tuple[str, datetime.date], tuple[datetime.date, datetime.date, float]]:
    """`[(slug, reported_date, release_month, value)]` -> one value per month.

    Precedence, in order: the LATEST reported date inside the calendar
    month, then the LATEST release to print that date. See the module
    docstring for why each half is there -- rule 1 keeps a financial-year
    anchor from displacing a genuine month-end, rule 2 makes a
    restatement supersede a first print.
    """
    best: dict[tuple[str, datetime.date],
               tuple[datetime.date, datetime.date, float]] = {}
    for slug, reported, release_month, value in candidates:
        key = (slug, reported.replace(day=1))
        prev = best.get(key)
        if prev is None or (reported, release_month) >= (prev[0], prev[1]):
            best[key] = (reported, release_month, value)
    return best


def _display(section: str, raw_label: str, statement: int) -> str:
    where = "Statement 1" if statement == 1 else "Statement 2"
    num = f"{section} " if section else ""
    name = re.sub(r"\s+", " ", raw_label)
    name = re.sub(r"^(?:[IVX]+|\d+(?:\.\d+)*)\s*[.)]\s*", "", name)
    name = re.sub(r"(?<=[A-Za-z)\]])\d$", "", name).strip()
    return (f"RBI Sectoral Deployment of Bank Credit — {num}{name} "
            f"(outstanding, Rs crore, {where})")[:255]


def run_fetch(
    since: str | None,
    until: str | None,
) -> tuple[list[IndicatorRow], list[ObservationRow]]:
    from playwright.sync_api import sync_playwright

    since_dt = datetime.date.fromisoformat(since) if since else None
    until_dt = datetime.date.fromisoformat(until) if until else None
    now = datetime.datetime.now(UTC)

    print("indexing releases...")
    rel = resolve_xlsx(list_releases(since_dt))
    if not rel:
        print("  no releases with an XLSX attachment")
        return [], []
    print(f"  {len(rel)} release(s): {rel[-1]['label']} .. {rel[0]['label']}")

    # Oldest first, so a later release's revision lands after the print it
    # revises and the "newest release wins" rule below reads naturally.
    rel.sort(key=lambda r: r["report_month"])

    with sync_playwright() as pw:
        got = download_all(pw, PROFILE,
                           [(r["label"], r["xlsx"]) for r in rel], DL_DIR)
    if not got:
        print("  no XLSX downloaded (TSPD block, or headed Chrome unavailable)")
        return [], []

    meta: dict[str, tuple[str, str, int]] = {}   # slug -> (section, label, stmt)
    candidates: list[tuple[str, datetime.date, datetime.date, float]] = []

    for r in rel:
        path = got.get(r["label"])
        if path is None:
            continue
        print(f"  parsing {r['label']}")
        wb = openpyxl.load_workbook(str(path), read_only=True, data_only=True)
        try:
            for idx, sheet in enumerate(wb.sheetnames[:2], start=1):
                labels, obs = parse_statement(_sheet_rows(wb[sheet]), idx)
                for slug, (section, raw) in labels.items():
                    # Deliberately NARROWER than the within-release guard in
                    # `parse_statement`, which also rejects a section-number
                    # mismatch. Across releases a renumbering is expected and
                    # must not raise -- that is the whole point of slugging on
                    # the name. The residual risk this accepts: if RBI ever
                    # reuses an existing label for a DIFFERENT concept in a
                    # later release, the two merge into one series silently.
                    # Not seen across the 65-release archive (2026-09-15); the
                    # published-YoY tie-out in the doc is the check that would
                    # notice.
                    prior = meta.get(slug)
                    if prior is not None and prior[2] != idx:
                        raise ValueError(
                            f"slug {slug!r} claimed by both statement "
                            f"{prior[2]} ({prior[1]!r}) and statement {idx} "
                            f"({raw!r}) in release {r['label']}"
                        )
                    meta.setdefault(slug, (section, raw, idx))
                for slug, d, v in obs:
                    candidates.append((slug, d, r["report_month"], v))
        finally:
            wb.close()

    best = resolve_months(candidates)

    indicators = [
        IndicatorRow(
            imdr_code=f"{PREFIX}.{slug}.IN",
            vendor_name=VENDOR,
            source_code=f"sibc/statement{stmt}/{section or slug.lower()}",
            display_name=_display(section, raw, stmt),
            unit="inr_cr",
            frequency="MONTHLY",
            country_iso="IN",
            category="credit",
            is_seasonally_adjusted=False,
            bbg_ticker=None,
        )
        for slug, (section, raw, stmt) in sorted(meta.items())
    ]

    observations = [
        ObservationRow(
            imdr_code=f"{PREFIX}.{slug}.IN",
            obs_date=month,
            vintage=0,
            release_date=now,
            value=value,
            ingested_at=now,
        )
        for (slug, month), (_reported, _rel_month, value) in sorted(best.items())
    ]

    print(f"  parsed: {len(indicators)} indicators / {len(observations)} obs")
    if since_dt or until_dt:
        observations = [
            o for o in observations
            if (since_dt is None or o.obs_date >= since_dt)
            and (until_dt is None or o.obs_date <= until_dt)
        ]
        print(f"  after date filter: {len(observations)} obs")
    return indicators, observations


def main() -> int:
    return run_main(
        vendor="rbi",
        topic="sectoral_credit",
        fetch_fn=run_fetch,
        description=("RBI Sectoral Deployment of Bank Credit — ~89 monthly "
                     "outstanding series by sector and industry (Rs crore)"),
        country_code="IN",
    )


if __name__ == "__main__":
    sys.exit(main())
