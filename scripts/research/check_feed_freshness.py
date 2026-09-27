"""Feed-freshness check for Spider digests (daily + weekly).

Answers one question mechanically, so no edition has to guess it: **for each
market-data family the digest quotes, what is the latest observation actually
in IMDR at the cut, and is that stale?**

This exists because of a real failure. The 25 and 26 Aug 2026 daily editions
both printed *"FRED credit, VIX and cash-Treasury series have not loaded past
19 August"* — the 26th escalating to *"now seven sessions stale ... second
consecutive edition"*. All of it was false: at the 26 Aug cut the credit OAS
and VIX blocks held observations through 24 Aug, ingested that same morning,
and the lane had not missed a business day. Two editions suppressed a credit
and volatility read that was sitting in ``econ.vw_fact_indicator_latest``.

Two things went wrong, and this script blocks both:

1. **Carried-forward claims.** The 26th said "still not loaded" — it trusted
   its own prior edition instead of re-querying. Staleness is a fact about the
   database at *this* cut and must be measured at every cut.
2. **Cadence confusion.** ``19 Aug`` was most likely read off the *weekly*
   NFCI block (``FRED.SENTIMENT.NFCI_CREDIT.US`` reads as "credit" but is a
   Chicago Fed weekly, Wednesday release for the prior Friday — it was
   perfectly on schedule). A weekly series must never be judged on a daily
   series' tolerance, so every family declares its own cadence and lag.

Staleness is measured in **business days** between the family's latest
``obs_date`` and the as-of date, minus the source's own publication lag. FRED
H.15 lands T+1, so an observation for 24 Aug at an 08:00 SGT 26 Aug cut is
*current*, not stale.

Usage::

    python scripts/research/check_feed_freshness.py
    python scripts/research/check_feed_freshness.py --as-of 2026-08-26
    python scripts/research/check_feed_freshness.py --family "credit OAS" --family VIX
    python scripts/research/check_feed_freshness.py --code "FRED.RATES.UST%"

Exit code 0 = every family within tolerance; 1 = at least one genuinely stale
family (or a bad argument / no matching series). Run it before locking a digest
MD and quote its output rather than a remembered number — see spider.md.
"""
from __future__ import annotations

import argparse
import datetime as dt
import sys

from sqlalchemy import bindparam, text

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass


# ---------------------------------------------------------------------------
# Family registry
#
# Each family is a LIKE pattern over econ.dim_indicator.imdr_code plus the
# cadence it is actually published on. `lag_days` is the source's own
# publication lag in business days: the number of business days after an
# observation's date that it first becomes fetchable. Tolerance is
# `lag_days + grace`, so a family is only flagged when it is behind by more
# than its own release schedule explains.
# ---------------------------------------------------------------------------

WEEKLY = "WEEKLY"
DAILY = "DAILY"


class Family:
    """One named group of indicators judged on a shared cadence."""

    def __init__(
        self,
        name: str,
        pattern: str,
        cadence: str,
        lag_days: int,
        grace: int = 1,
        note: str = "",
        calendar_code: str = "FD",
    ) -> None:
        self.name = name
        self.pattern = pattern
        self.cadence = cadence
        self.lag_days = lag_days
        self.grace = grace
        self.note = note
        # Market calendar whose holidays don't count as business days for this
        # family (calendar.dim_calendar.calendar_code). Defaults to the Federal
        # Reserve Board calendar, which is right for every FRED family.
        self.calendar_code = calendar_code

    @property
    def tolerance(self) -> int:
        """Max business days behind as-of before the family is called stale."""
        if self.cadence == WEEKLY:
            # A weekly series is up to a full week behind by construction.
            return self.lag_days + 5 + self.grace
        return self.lag_days + self.grace


REGISTRY: list[Family] = [
    Family(
        "credit OAS", "FRED.CREDIT.%OAS%", DAILY, lag_days=2,
        note="ICE BofA OAS via FRED. T+2 at our cut, NOT T+1: every "
             "observation lands on the ~02:30 SGT run two calendar days "
             "after obs_date, because FRED posts these in the US afternoon "
             "(after our ~21:00 SGT run) and the next run is ~02:30. "
             "Measured over 2026-08-10..09-07: every obs arrived at the "
             "02:30-04:00 run, lag 2 calendar days (4 across a weekend). "
             "At lag_days=1 the tolerance equalled the structural lag, so "
             "the family sat exactly on the boundary and flipped "
             "OK/STALE on any perturbation -- a holiday, a skipped weekend "
             "02:30 run, or simply being evaluated before that run.",
    ),
    Family(
        "volatility", "FRED.SENTIMENT.V[XI]%", DAILY, lag_days=2,
        note="VIX / VXN via FRED; same T+2 arrival as the credit OAS block "
             "(they share the run).",
    ),
    Family(
        "cash Treasuries", "FRED.RATES.UST[_]%", DAILY, lag_days=2,
        note="Treasury constant-maturity curve (DGS*, H.15). Publishes T+2 at "
             "our ~08:30 SGT cut, NOT T+1: FRED posts the derived spread and "
             "breakeven series (T10Y2Y/T10YIE) a full business day before the "
             "DGS*/DFII* levels they are computed from. Verified against the "
             "FRED API 2026-09-09 - DGS10 ended 09-04 while T10Y2Y already "
             "held 09-08. A one-business-day lead of derived over inputs is "
             "therefore NORMAL and is not an IMDR ingest defect.",
    ),
    Family(
        "breakevens", "FRED.RATES.BEI%", DAILY, lag_days=1,
    ),
    Family(
        "curve spreads", "FRED.RATES.CURVE[_]%", DAILY, lag_days=1,
        note="T10Y2Y / T10Y3M. Previously UNMONITORED - the registry had no "
             "CURVE pattern, so a stall here would have gone unseen.",
    ),
    Family(
        "TIPS real yields", "FRED.RATES.TIPS%", DAILY, lag_days=2,
        note="DFII* real yields; same T+2 H.15 quirk as the UST block.",
    ),
    Family(
        "NFCI block", "FRED.SENTIMENT.%NFCI%", WEEKLY, lag_days=3,
        note="Chicago Fed NFCI: Wednesday release for the prior Friday. "
             "NFCI_CREDIT is a WEEKLY credit subindex — it is NOT the daily "
             "credit OAS block; never generalise its cadence to that block.",
    ),
    Family(
        "energy spot (EIA)", "EIA.ENERGY.%", WEEKLY, lag_days=2,
        note="Brent (RBRTE), WTI (RWTC) and Henry Hub via the EIA v2 API. "
             "DAILY observations delivered in a WEEKLY Thursday batch: "
             "ingests on 07-23/07-30/08-06/08-13/08-20/08-27/09-03 were all "
             "Thursdays ~02:30-03:30 SGT, each carrying a block of five "
             "daily obs ending 2 calendar days back. So a mid-week plateau "
             "is the normal state and must not be read as a dead feed -- "
             "judging this on a DAILY tolerance is the same cadence error "
             "that produced the phantom NFCI outage.\n"
             "   NOTE: this is IMDR's ONLY Brent price source. Citi's "
             "COMMODITIES.SPOT namespace holds just three tags "
             "(OIL_PRICE_NYMEX, SPOT_GOLD, SPOT_SILVER) with no Brent spot, "
             "the FRED DCOILBRENTEU/DCOILWTICO duplicates are is_active=0 "
             "(migration 106) and mirror this same EIA data anyway, and "
             "BBG\\Commodities died in 2023. IMDR therefore cannot source a "
             "same-day Brent print at all; the best achievable is ~T-2, "
             "refreshed weekly. Quote the vintage, or attribute to sell-side.",
    ),
    Family(
        "IMD rainfall (cumulative)", "IMD.RAINFALL.AI.CUM.%", DAILY, lag_days=1,
        note="Season cumulative from 1 Jun; page updates 08:30 IST. "
             "Off-season the series stops legitimately.",
        calendar_code="RB",
    ),
]


# ---------------------------------------------------------------------------
# Derived-vs-input coherence
#
# FRED publishes the derived spread/breakeven series one business day ahead of
# the DGS*/DFII* levels they are computed from, so a 1-day lead is expected and
# benign. A LARGER lead is the dangerous direction: the input side has stalled
# while the derived side keeps advancing, and a consumer quoting only the curve
# would be reading fresh numbers sitting on stale inputs. Each tuple is
# (derived family, input family, max expected lead in business days).
# ---------------------------------------------------------------------------

COHERENCE_PAIRS: list[tuple[str, str, int]] = [
    ("curve spreads", "cash Treasuries", 1),
    ("breakevens", "cash Treasuries", 1),
    ("breakevens", "TIPS real yields", 1),
]


# ---------------------------------------------------------------------------
# Business-day arithmetic
# ---------------------------------------------------------------------------

def business_days_between(
    start: dt.date,
    end: dt.date,
    holidays: frozenset = frozenset(),
) -> int:
    """Count trading days strictly after `start`, up to `end`.

    Mon-Fri minus the market holidays in `holidays`, so weekend- and
    holiday-only gaps score 0. Holidays are modelled deliberately: with the
    plain Mon-Fri count the H.15 families tripped a false STALE every holiday
    week -- on 2026-09-09 the UST block read "3 business days behind" purely
    because US Labor Day (Mon 2026-09-07) was counted as a business day. A
    checker that cries stale on every long weekend trains its reader to ignore
    it, which is the failure it exists to prevent.
    """
    if end <= start:
        return 0
    n = 0
    cur = start
    while cur < end:
        cur += dt.timedelta(days=1)
        if cur.weekday() < 5 and cur not in holidays:
            n += 1
    return n


_HOLIDAY_SQL = """
SELECT DISTINCT c.calendar_code, h.holiday_date
  FROM calendar.market_holidays h
  JOIN calendar.dim_calendar c ON c.id = h.calendar_id
 WHERE c.calendar_code IN :codes
"""


def load_holidays(conn, codes: set) -> dict:
    """Return {calendar_code: frozenset(holiday dates)} for `codes`."""
    if not codes:
        return {}
    stmt = text(_HOLIDAY_SQL).bindparams(bindparam("codes", expanding=True))
    acc = {c: set() for c in codes}
    for code, day in conn.execute(stmt, {"codes": sorted(codes)}):
        acc.setdefault(code, set()).add(_as_date(day))
    return {k: frozenset(v) for k, v in acc.items()}


# ---------------------------------------------------------------------------
# Query
# ---------------------------------------------------------------------------

_SQL = """
SELECT COUNT(DISTINCT i.id)        AS n_series,
       MAX(f.obs_date)             AS latest_obs,
       MAX(f.ingested_at)          AS latest_ingest
  FROM econ.dim_indicator i
  JOIN econ.fact_indicator f ON f.indicator_id = i.id
 WHERE i.is_active = 1
   AND i.imdr_code LIKE :pattern
"""


def probe(conn, pattern: str) -> dict:
    row = conn.execute(text(_SQL), {"pattern": pattern}).one()
    return {
        "n_series": int(row[0] or 0),
        "latest_obs": row[1],
        # MAX(ingested_at) = when this family last gained a NEW row, which is
        # NOT when its pipeline last ran: the econ loader skips unchanged
        # values, and econ pipelines register nothing in audit.pipeline_runs
        # (only commodities/equities/fx/rates do). So a date here that looks
        # old means "no new data since", never "the job stopped".
        "latest_ingest": row[2],
    }


def _as_date(value) -> dt.date:
    """Narrow whatever the driver hands back to a plain ``date``.

    The ``SQL Server`` ODBC driver this project pins returns DATE columns as
    ISO strings rather than ``datetime.date``, so string input is the normal
    path here, not an edge case.
    """
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    return dt.date.fromisoformat(str(value)[:10])


def evaluate(
    fam: Family,
    result: dict,
    as_of: dt.date,
    holidays: frozenset = frozenset(),
) -> dict:
    """Fold a probe result into a verdict for one family."""
    if not result["n_series"] or result["latest_obs"] is None:
        return {**result, "family": fam, "behind": None, "status": "MISSING"}

    latest_obs = _as_date(result["latest_obs"])
    behind = business_days_between(latest_obs, as_of, holidays)
    status = "OK" if behind <= fam.tolerance else "STALE"
    return {
        **result,
        "family": fam,
        "latest_obs": latest_obs,
        "behind": behind,
        "status": status,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def check_coherence(verdicts: list[dict], holidays: dict) -> list[str]:
    """Flag derived families running further ahead of their inputs than normal.

    Returns a list of warning lines (empty when every pair is coherent). This
    catches the asymmetric failure the plain per-family staleness check cannot:
    the derived series advancing on schedule while its inputs sit still, so a
    report quoting only the curve shows fresh data built on stale levels.
    """
    by_name = {v["family"].name: v for v in verdicts}
    out: list[str] = []
    for derived_name, input_name, max_lead in COHERENCE_PAIRS:
        d, i = by_name.get(derived_name), by_name.get(input_name)
        if not d or not i or not d["latest_obs"] or not i["latest_obs"]:
            continue  # family not selected this run, or MISSING
        cal = holidays.get(d["family"].calendar_code, frozenset())
        lead = business_days_between(_as_date(i["latest_obs"]),
                                     _as_date(d["latest_obs"]), cal)
        if lead > max_lead:
            out.append(
                f"!! INCOHERENT: {derived_name} ({d['latest_obs']}) leads "
                f"{input_name} ({i['latest_obs']}) by {lead} business days, "
                f"max expected {max_lead}. The derived series is advancing "
                f"without its inputs — do NOT quote it as a current read."
            )
    return out


def _select(names: list[str] | None, codes: list[str] | None) -> list[Family]:
    if codes:
        return [Family(p, p, DAILY, lag_days=1) for p in codes]
    if not names:
        return list(REGISTRY)
    wanted = {n.casefold() for n in names}
    picked = [f for f in REGISTRY if f.name.casefold() in wanted]
    missing = wanted - {f.name.casefold() for f in picked}
    if missing:
        print(f"!! unknown family: {sorted(missing)}", file=sys.stderr)
        print(f"   known: {[f.name for f in REGISTRY]}", file=sys.stderr)
        return []
    return picked


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--as-of", default=None,
                    help="Edition cut date, YYYY-MM-DD (default: today, local).")
    ap.add_argument("--family", action="append", default=None,
                    help="Restrict to a named family; repeatable.")
    ap.add_argument("--code", action="append", default=None,
                    help="Ad-hoc imdr_code LIKE pattern; repeatable. "
                         "Overrides --family.")
    args = ap.parse_args(argv)

    if args.as_of:
        try:
            as_of = dt.date.fromisoformat(args.as_of)
        except ValueError:
            print(f"!! --as-of must be YYYY-MM-DD, got {args.as_of!r}",
                  file=sys.stderr)
            return 1
    else:
        as_of = dt.date.today()

    families = _select(args.family, args.code)
    if not families:
        return 1

    # Imported here so --help works without DB settings present.
    from imdr.config.settings import get_settings
    from imdr.connectors.mssql import MSSQLConnector

    connector = MSSQLConnector(get_settings())
    verdicts = []
    try:
        with connector.read_engine.connect() as conn:
            holidays = load_holidays(conn, {f.calendar_code for f in families})
            for fam in families:
                verdicts.append(evaluate(
                    fam, probe(conn, fam.pattern), as_of,
                    holidays.get(fam.calendar_code, frozenset()),
                ))
    finally:
        connector.dispose()

    print(f"Feed freshness as of {as_of.isoformat()} "
          f"({as_of.strftime('%a')}) — business days behind\n")
    header = f"{'family':<28} {'series':>6} {'latest obs':>12} {'behind':>7} {'tol':>4}  status"
    print(header)
    print("-" * len(header))
    for v in verdicts:
        fam = v["family"]
        obs = v["latest_obs"].isoformat() if v["latest_obs"] else "—"
        behind = "—" if v["behind"] is None else str(v["behind"])
        print(f"{fam.name:<28} {v['n_series']:>6} {obs:>12} "
              f"{behind:>7} {fam.tolerance:>4}  {v['status']}")

    stale = [v for v in verdicts if v["status"] != "OK"]
    print()
    for v in stale:
        fam = v["family"]
        if v["status"] == "MISSING":
            print(f"!! {fam.name}: no active series match "
                  f"'{fam.pattern}' — pattern drift or the feed was retired.")
        else:
            print(f"!! {fam.name}: latest obs {v['latest_obs']} is "
                  f"{v['behind']} business days behind {as_of} "
                  f"(tolerance {fam.tolerance}, {fam.cadence.lower()} cadence, "
                  f"newest row written {v['latest_ingest']}).")
        if fam.note:
            print(f"   {fam.note}")

    incoherent = check_coherence(verdicts, holidays)
    for line in incoherent:
        print(line)

    if not stale and not incoherent:
        print("All families within tolerance — quote these dates, "
              "do not carry a staleness claim forward from a prior edition.")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
