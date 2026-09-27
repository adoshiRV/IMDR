"""RBI DBIE — Scheduled Commercial Banks' aggregate business in India.

The other half of **DG24**: alongside the sectoral deployment table
(`rbi_sectoral_credit.py`), the gap asks for "aggregate
scheduled-commercial-bank business in India — total bank credit and total
deposits". That pair is what the credit-deposit gap, the credit-deposit
ratio and the deposit-growth line on the dashboard are computed from, and
none of it existed in IMDR.

Scraped through the shared SAP-BO flow in
`imdr.domains.econ.rbi_dbie_sapbo` -- the same flow the two live fetchers
for reportIds 417 and 698 already use:

  reportId 1130  Food & Non-Food Credit of Scheduled Commercial Banks
                 -> BANK_CREDIT · FOOD_CREDIT · NON_FOOD_CREDIT

**The deposits half of DG24 is NOT served yet, and this fetcher says so
rather than shipping something flaky.** reportId 9 ("Scheduled Commercial
Banks - Business in India") carries aggregate / demand / time deposits,
but its SAP-BO grid is HORIZONTALLY PANelled and the DOM scrape lands on
a different panel from run to run: three live scrapes on 2026-09-15
returned, in order, a 101-row monthly panel whose 15 columns included
`2.1 Aggregate Deposits`, and then twice a 748-row fortnightly panel
(back to Jun-1997) carrying only the four interbank-liability columns and
no deposits at all. `scrape_iframe_table` picks the largest leaf table by
row count, so the deeper panel now wins and the deposits columns are
simply not in the DOM. Reaching them needs the grid's horizontal scroll
or its Export button, which is a separate piece of work; see
`BLOCKED_REPORTS` below and the doc page. Emitting whichever panel turned
up would make the series set depend on a race.

**This is a DIFFERENT UNIVERSE from `INDIA.SECTORAL_CREDIT.*` and gets
its own prefix for exactly that reason.** These are Section-42 returns
covering ALL scheduled commercial banks; the sectoral release covers ~41
select banks accounting for about 95% of non-food credit. DG24 names the
confusion as one of its two traps: bars sourced from the two cannot share
an as-of stamp even when they share a month. Two prefixes make that
structural rather than a footnote.

**Grain.** Both reports are published fortnightly, and IMDR's frequency
vocabulary (`dbo.dim_frequency`, 11 rows) has no FORTNIGHTLY member. So
this fetcher keeps the LAST reporting fortnight of each month and
declares MONTHLY -- the grain the dashboard card plots, the grain RBI
itself headlines, and the same bucketing `rbi_sectoral_credit.py` uses,
so the two are directly comparable. The mid-month print is dropped, not
lost: it is one migration (seeding a FORTNIGHTLY row) and a one-line
change away, and that decision is deliberately left open rather than
taken here.

**Known upstream defect, handled.** Report 1130 publishes rows where
Bank Credit is blank and Non-Food Credit is reported as the NEGATIVE of
Food Credit -- i.e. it computes `0 - food` when the credit figure has not
landed. Seen on 2026-06-30 and 2026-04-30 in the live scrape of
2026-09-15. A row with no Bank Credit is dropped whole; taking the
non-food figure at face value would write a negative credit stock.

HEADED Chrome required (the SAP-BO iframe refuses to authenticate
headless), and STRICTLY SEQUENTIAL with every other DBIE fetcher -- they
share one Chrome profile dir and `launch_persistent_context` takes an
exclusive lock on it.

Run (prod, loads to DB):
    python -m scripts.econ.in.rbi.rbi_dbie_scb_business

Run (smoke, no DB write):
    python -m scripts.econ.in.rbi.rbi_dbie_scb_business --no-load
"""
from __future__ import annotations

import datetime
import re
import sys

from imdr.domains.econ.rbi_dbie_sapbo import launch_dbie_context, search_click_scrape
from imdr.domains.econ.rbi_parse import parse_date, parse_number
from imdr.domains.econ.schema import IndicatorRow, ObservationRow
from scripts.econ._runner import run_main

UTC = datetime.timezone.utc

PREFIX = "INDIA.SCB_BUSINESS"
VENDOR = "RBI"

# `search` is typed into the DBIE search box; `match` is the substring the
# result <a> must contain. They differ where the title carries a character
# the search box chokes on -- an "&" returns zero hits (reportId 1130).
REPORTS: list[dict] = [
    {
        "report_id": "1130",
        "search": "Non-Food Credit of Scheduled Commercial Banks",
        "match": "Non-Food Credit of Scheduled Commercial Banks",
        # Column header (normalised) -> (slug, display suffix). Keyed on
        # TEXT, not position: the SAP-BO DOM scrape returns one horizontal
        # panel of a wider table, so column indices are not stable.
        "columns": {
            "BANK_CREDIT": ("BANK_CREDIT", "Bank credit, all SCBs"),
            "FOOD_CREDIT": ("FOOD_CREDIT", "Food credit, all SCBs"),
            "NON_FOOD_CREDIT": ("NON_FOOD_CREDIT", "Non-food credit, all SCBs"),
        },
        # Drop the whole row when this column is missing -- see the
        # module docstring on report 1130's negative non-food rows.
        "require": "BANK_CREDIT",
    },
]

# Not scraped. Kept as a record of what was probed and why it does not
# run, so the next person does not re-derive it -- see the module
# docstring for the panel race. Everything below is verified live
# (2026-09-15) and correct AS A MAP; it is the DELIVERY that is unsafe.
BLOCKED_REPORTS: list[dict] = [
    {
        "report_id": "9",
        "search": "Business in India",
        "match": "Scheduled Commercial Banks - Business in India",
        "blocked": "SAP-BO horizontal panel race — deposits columns absent "
                   "from the panel the DOM scrape now returns",
        "columns": {
            "AGGREGATE_DEPOSITS": ("AGGREGATE_DEPOSITS",
                                   "Aggregate deposits, all SCBs"),
            "DEMAND": ("DEMAND_DEPOSITS", "Demand deposits, all SCBs"),
            "TIME": ("TIME_DEPOSITS", "Time deposits, all SCBs"),
            "LIABILITIES_TO_OTHERS": ("LIABILITIES_TO_OTHERS",
                                      "Liabilities to others, all SCBs"),
            "LIABILITIES_TO_THE_BANKING_SYSTEM": (
                "LIABILITIES_TO_BANKING_SYSTEM",
                "Liabilities to the banking system, all SCBs"),
            "BORROWINGS_FROM_RESERVE_BANK": (
                "BORROWINGS_FROM_RBI", "Borrowings from the Reserve Bank"),
            "NUMBER_OF_REPORTING_BANKS": (
                "REPORTING_BANKS", "Number of reporting banks"),
        },
        "require": "AGGREGATE_DEPOSITS",
    },
]

# Every column on these reports is a Rs.-crore stock except the bank count.
_COUNT_SLUGS = {"REPORTING_BANKS"}


def _norm_header(text: str) -> str:
    """`'2.1 AggregateDeposits'` -> `'AGGREGATE_DEPOSITS'`.

    The SAP-BO DOM strips the line breaks inside a wrapped header cell
    without putting a space back, so `Aggregate` and `Deposits` arrive
    fused. Split on the lower->upper boundary before slugging, or every
    multi-word column misses its map entry.
    """
    s = re.sub(r"\s+", " ", str(text or "")).strip()
    s = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", s)
    s = re.sub(r"^(?:[\d.]+|[IVX]+)\s*[.)]?\s*", "", s)
    s = re.sub(r"\([^)]*\)", " ", s)
    s = re.sub(r"[^A-Za-z0-9]+", "_", s).strip("_").upper()
    return re.sub(r"_+", "_", s)


def _matcher_for(match: str):
    def _m(page):
        return page.locator("a").filter(has_text=match)
    return _m


def parse_report(
    table_rows: list[list[str]],
    spec: dict,
) -> tuple[dict, list[tuple]]:
    """One scraped DBIE table -> ({slug: display}, [(slug, date, value)]).

    Row 0 is the header; column 0 is the reporting date. Only the columns
    named in `spec["columns"]` are emitted -- report 9 carries 31 columns
    of which the DOM scrape returns 15, and taking whatever turns up
    would make the series set depend on how SAP-BO happened to paginate.
    """
    if not table_rows:
        return {}, []

    header = [_norm_header(c) for c in table_rows[0]]
    wanted: dict[int, tuple[str, str]] = {}
    for i, name in enumerate(header):
        if i == 0:
            continue
        hit = spec["columns"].get(name)
        if hit:
            wanted[i] = hit
    if not wanted:
        print(f"    reportId {spec['report_id']}: no mapped columns in "
              f"{header[:8]} — layout changed, emitting nothing")
        return {}, []

    require_slug = spec["columns"].get(spec["require"], (None,))[0]
    labels = {slug: disp for slug, disp in wanted.values()}
    obs: list[tuple] = []
    dropped = 0

    for row in table_rows[1:]:
        if not row:
            continue
        d = parse_date(row[0])
        if d is None:
            continue
        values: dict[str, float] = {}
        for i, (slug, _disp) in wanted.items():
            v = parse_number(row[i]) if i < len(row) else None
            if v is not None:
                values[slug] = v
        if require_slug is not None and require_slug not in values:
            # The upstream row is incomplete and its derived columns are
            # arithmetic on a missing figure. Drop it whole.
            dropped += 1
            continue
        for slug, v in values.items():
            obs.append((slug, d, v))

    if dropped:
        print(f"    reportId {spec['report_id']}: dropped {dropped} "
              f"incomplete row(s) missing {spec['require']}")
    return labels, obs


def _last_fortnight_per_month(obs: list[tuple]) -> dict[tuple[str, datetime.date], tuple[datetime.date, float]]:
    """Keep the latest reporting date within each calendar month."""
    best: dict[tuple[str, datetime.date], tuple[datetime.date, float]] = {}
    for slug, d, v in obs:
        key = (slug, d.replace(day=1))
        prev = best.get(key)
        if prev is None or d > prev[0]:
            best[key] = (d, v)
    return best


def run_fetch(
    since: str | None,
    until: str | None,
) -> tuple[list[IndicatorRow], list[ObservationRow]]:
    from playwright.sync_api import sync_playwright

    since_dt = datetime.date.fromisoformat(since) if since else None
    until_dt = datetime.date.fromisoformat(until) if until else None
    now = datetime.datetime.now(UTC)

    labels: dict[str, str] = {}
    raw: list[tuple] = []

    with sync_playwright() as pw:
        ctx = launch_dbie_context(pw)
        try:
            for spec in REPORTS:
                print(f"  reportId {spec['report_id']} — {spec['search']}")
                rows = search_click_scrape(
                    ctx, spec["search"], _matcher_for(spec["match"]),
                    max_attempts=3,
                )
                if not rows:
                    print(f"    no rows scraped for {spec['report_id']}")
                    continue
                got_labels, got_obs = parse_report(rows, spec)
                labels.update(got_labels)
                raw.extend(got_obs)
                print(f"    {len(got_labels)} series / {len(got_obs)} raw obs")
        finally:
            ctx.close()

    if not raw:
        return [], []

    monthly = _last_fortnight_per_month(raw)

    indicators = [
        IndicatorRow(
            imdr_code=f"{PREFIX}.{slug}.IN",
            vendor_name=VENDOR,
            source_code=f"dbie/scb_business/{slug.lower()}",
            display_name=(
                f"RBI DBIE Scheduled Commercial Banks — {display} "
                f"({'count' if slug in _COUNT_SLUGS else 'Rs crore'}, "
                f"last reporting fortnight of month)")[:255],
            unit="count" if slug in _COUNT_SLUGS else "inr_cr",
            frequency="MONTHLY",
            country_iso="IN",
            category="credit",
            is_seasonally_adjusted=False,
            bbg_ticker=None,
        )
        for slug, display in sorted(labels.items())
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
        for (slug, month), (_d, value) in sorted(monthly.items())
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
        topic="dbie_scb_business",
        fetch_fn=run_fetch,
        description=("RBI DBIE reportIds 1130 + 9 — aggregate SCB bank credit "
                     "and deposits (Rs crore, month-end reporting fortnight)"),
        country_code="IN",
    )


if __name__ == "__main__":
    sys.exit(main())
