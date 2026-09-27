"""KSD — CD (certificate of deposit) primary-market ISSUANCE + OUTSTANDING.

Source: 금융위원회 (FSC) 단기금융증권 발행정보 open API, data.go.kr org
**1160100**, operation ``getCdIssuBasiInfo_V2``:

    https://apis.data.go.kr/1160100/GetShorTermSecuIssuInfoService_V2/getCdIssuBasiInfo_V2

Same underlying KSD (Korea Securities Depository) registration data as the
originally-scoped dataset #15059591, reached via the newer FSC-published org
1160100 — verified live 2026-08-04 (see
``docs/admin/econ/korea/fsc_short_term_securities.md``). Reuses the ``ksd``
vendor (migration 115) — no new vendor, no new migration.

Auth gotcha: ``IMDR_KSD_API_KEY`` in `.env` is the URL-ENCODED ("Encoding")
variant (ends ``%3D%3D``). It must go RAW into the query string — passed
through ``requests(params=...)`` it gets double-encoded and auth silently
fails. See ``imdr.domains.econ.datagokr_http`` for the raw-URL builder.

**Snapshot semantics (the load-bearing gotcha of this fetcher):** each row's
``basDt`` is a DAILY SNAPSHOT DATE, not the issue date — every CD (``isinCd``,
immutable) appears in every daily snapshot from its ``codpIssuDt`` until it
matures (``codpExprDt``). So:
  - **Issuance FLOW** (new CDs issued on a given date) = dedup rows by
    ``isinCd`` first, then group the *one* row per CD by ``codpIssuDt``.
  - **Outstanding STOCK** (total live CD book on a given date) = for one
    ``basDt`` snapshot, sum ``codpIssuAmt`` across all its rows (no dedup —
    the repetition across snapshots IS the outstanding book).
Indicators (vendor ``ksd``, country KR, frequency DAILY, category liquidity
unless noted):
    KSD.CD.ISSUANCE.VOLUME.KR    Σ codpIssuAmt (krw_bn) per issue date (FLOW)
    KSD.CD.ISSUANCE.COUNT.KR     new CD issues per issue date (FLOW, count)
    KSD.CD.ISSUANCE.AVG_RATE.KR  issuance-amount-weighted codpDcRat, % (FLOW, category rates)
    KSD.CD.OUTSTANDING.KR        Σ codpIssuAmt (krw_bn) per basDt snapshot (STOCK)

Live mode probes basDt back from T-1 (skipping weekends/holidays) for the
latest available snapshot, pages it (~300 rows, one page), emits OUTSTANDING
for that basDt plus FLOW for any codpIssuDt within the trailing lookback
window (recently-issued CDs are all still in the book — none have matured —
so those issue-date totals are already complete from a single snapshot).
Backfill mode (``--since``) pages the ENTIRE dataset once (no basDt filter),
which is the only way to recover FLOW/STOCK history predating recent
snapshots (~577 pages @ numOfRows=1000; a one-off, not part of the daily run).

Usage:
    python -m scripts.econ.kr.ksd.ksd_cd_issuance                    # live (latest snapshot)
    python -m scripts.econ.kr.ksd.ksd_cd_issuance --since 2020-01-01  # full backfill
"""

from __future__ import annotations

import datetime
import os
from collections import defaultdict
from pathlib import Path

from imdr.domains.econ.datagokr_http import fetch_datagokr_rows, make_session
from imdr.domains.econ.schema import IndicatorRow, ObservationRow
from scripts.econ._runner import run_main

UTC = datetime.timezone.utc
_REPO_ROOT = Path(__file__).resolve().parents[4]
_SERVICE_URL = (
    "https://apis.data.go.kr/1160100/GetShorTermSecuIssuInfoService_V2/"
    "getCdIssuBasiInfo_V2"
)
_HISTORY_START = datetime.date(2020, 1, 1)
_LIVE_ISSUE_LOOKBACK_DAYS = 40
_MAX_PROBE_DAYS = 10  # covers a long Korean holiday run (e.g. Chuseok/Lunar NY)

_CODES = {
    "VOLUME": "KSD.CD.ISSUANCE.VOLUME.KR",
    "COUNT": "KSD.CD.ISSUANCE.COUNT.KR",
    "AVG_RATE": "KSD.CD.ISSUANCE.AVG_RATE.KR",
    "OUTSTANDING": "KSD.CD.OUTSTANDING.KR",
}


def _load_key() -> str | None:
    key = os.environ.get("IMDR_KSD_API_KEY")
    if key:
        return key
    env = _REPO_ROOT / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            if line.startswith("IMDR_KSD_API_KEY="):
                return line.split("=", 1)[1].strip() or None
    return None


def _parse_yyyymmdd(raw: object) -> datetime.date | None:
    if not raw:
        return None
    try:
        return datetime.datetime.strptime(str(raw), "%Y%m%d").date()
    except ValueError:
        return None


def _to_amount(raw: object) -> float | None:
    if raw in (None, ""):
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _fetch_snapshot(session, key: str, bas_dt: datetime.date) -> list[dict]:
    return fetch_datagokr_rows(
        session, _SERVICE_URL, key,
        {"basDt": bas_dt.strftime("%Y%m%d")},
        page_size=1000,
    )


def _probe_latest_snapshot(
    session, key: str, start: datetime.date,
) -> tuple[datetime.date, list[dict]] | None:
    """Walk back from `start` for the latest basDt with any rows."""
    for offset in range(_MAX_PROBE_DAYS):
        bas_dt = start - datetime.timedelta(days=offset)
        rows = _fetch_snapshot(session, key, bas_dt)
        if rows:
            return bas_dt, rows
    return None


def _dedup_by_isin(rows: list[dict]) -> dict[str, dict]:
    by_isin: dict[str, dict] = {}
    for r in rows:
        isin = r.get("isinCd")
        if isin and isin not in by_isin:
            by_isin[isin] = r
    return by_isin


def _flow_by_issue_date(
    isin_rows: dict[str, dict],
    since_dt: datetime.date,
    until_dt: datetime.date,
) -> dict[datetime.date, list[dict]]:
    grouped: dict[datetime.date, list[dict]] = defaultdict(list)
    for r in isin_rows.values():
        issue_dt = _parse_yyyymmdd(r.get("codpIssuDt"))
        if issue_dt is None or issue_dt < since_dt or issue_dt > until_dt:
            continue
        grouped[issue_dt].append(r)
    return grouped


def _stock_by_bas_dt(
    rows: list[dict],
    since_dt: datetime.date,
    until_dt: datetime.date,
) -> dict[datetime.date, float]:
    totals: dict[datetime.date, float] = defaultdict(float)
    for r in rows:
        bas_dt = _parse_yyyymmdd(r.get("basDt"))
        if bas_dt is None or bas_dt < since_dt or bas_dt > until_dt:
            continue
        amt = _to_amount(r.get("codpIssuAmt"))
        if amt is not None:
            totals[bas_dt] += amt
    return totals


def _indicator_rows() -> list[IndicatorRow]:
    return [
        IndicatorRow(
            imdr_code=_CODES["VOLUME"],
            vendor_name="KSD",
            source_code="datagokr/1160100/getCdIssuBasiInfo_V2/issuance_volume",
            display_name="Korea CD new issuance, volume (KRW bn) (KSD, data.go.kr 1160100)",
            unit="krw_bn",
            frequency="DAILY",
            country_iso="KR",
            category="liquidity",
            is_seasonally_adjusted=False,
            bbg_ticker=None,
        ),
        IndicatorRow(
            imdr_code=_CODES["COUNT"],
            vendor_name="KSD",
            source_code="datagokr/1160100/getCdIssuBasiInfo_V2/issuance_count",
            display_name="Korea CD new issuance, count (KSD, data.go.kr 1160100)",
            unit="count",
            frequency="DAILY",
            country_iso="KR",
            category="liquidity",
            is_seasonally_adjusted=False,
            bbg_ticker=None,
        ),
        IndicatorRow(
            imdr_code=_CODES["AVG_RATE"],
            vendor_name="KSD",
            source_code="datagokr/1160100/getCdIssuBasiInfo_V2/issuance_avg_rate",
            display_name="Korea CD new issuance, amount-weighted discount rate, % (KSD, data.go.kr 1160100)",
            unit="pct",
            frequency="DAILY",
            country_iso="KR",
            category="rates",
            is_seasonally_adjusted=False,
            bbg_ticker=None,
        ),
        IndicatorRow(
            imdr_code=_CODES["OUTSTANDING"],
            vendor_name="KSD",
            source_code="datagokr/1160100/getCdIssuBasiInfo_V2/outstanding",
            display_name="Korea CD outstanding balance (KRW bn) (KSD, data.go.kr 1160100)",
            unit="krw_bn",
            frequency="DAILY",
            country_iso="KR",
            category="liquidity",
            is_seasonally_adjusted=False,
            bbg_ticker=None,
        ),
    ]


def _flow_observations(
    grouped: dict[datetime.date, list[dict]], now: datetime.datetime,
) -> list[ObservationRow]:
    observations: list[ObservationRow] = []
    for issue_dt, group_rows in grouped.items():
        total_amt = 0.0
        weighted_rate_sum = 0.0
        for r in group_rows:
            amt = _to_amount(r.get("codpIssuAmt")) or 0.0
            rate = _to_amount(r.get("codpDcRat"))
            total_amt += amt
            if rate is not None:
                weighted_rate_sum += amt * rate
        avg_rate = weighted_rate_sum / total_amt if total_amt else None

        observations.append(ObservationRow(
            imdr_code=_CODES["VOLUME"], obs_date=issue_dt, vintage=0,
            release_date=now, value=total_amt / 1e9, ingested_at=now,
        ))
        observations.append(ObservationRow(
            imdr_code=_CODES["COUNT"], obs_date=issue_dt, vintage=0,
            release_date=now, value=float(len(group_rows)), ingested_at=now,
        ))
        if avg_rate is not None:
            observations.append(ObservationRow(
                imdr_code=_CODES["AVG_RATE"], obs_date=issue_dt, vintage=0,
                release_date=now, value=avg_rate, ingested_at=now,
            ))
    return observations


def _stock_observations(
    totals: dict[datetime.date, float], now: datetime.datetime,
) -> list[ObservationRow]:
    return [
        ObservationRow(
            imdr_code=_CODES["OUTSTANDING"], obs_date=bas_dt, vintage=0,
            release_date=now, value=total_amt / 1e9, ingested_at=now,
        )
        for bas_dt, total_amt in totals.items()
    ]


def run_fetch(
    since: str | None,
    until: str | None,
) -> tuple[list[IndicatorRow], list[ObservationRow]]:
    key = _load_key()
    if not key:
        print("  KSD CD-issuance: DORMANT — IMDR_KSD_API_KEY not set. Skipping.")
        return [], []

    now = datetime.datetime.now(UTC)
    today = datetime.date.today()
    indicators = _indicator_rows()
    session = make_session()

    if since is None:
        until_dt = (
            datetime.date.fromisoformat(until) if until
            else today - datetime.timedelta(days=1)
        )
        print(f"  Probing latest CD snapshot back from {until_dt} ...",
              end=" ", flush=True)
        probe = _probe_latest_snapshot(session, key, until_dt)
        if probe is None:
            print(f"no snapshot found in the last {_MAX_PROBE_DAYS} days")
            return indicators, []
        bas_dt, rows = probe
        print(f"basDt={bas_dt} ({len(rows)} rows)")

        isin_rows = _dedup_by_isin(rows)
        issue_since = bas_dt - datetime.timedelta(days=_LIVE_ISSUE_LOOKBACK_DAYS)
        grouped = _flow_by_issue_date(isin_rows, issue_since, bas_dt)
        stock_totals = _stock_by_bas_dt(rows, bas_dt, bas_dt)

        observations = _flow_observations(grouped, now) + _stock_observations(stock_totals, now)
        return indicators, observations

    since_dt = datetime.date.fromisoformat(since)
    if since_dt < _HISTORY_START:
        since_dt = _HISTORY_START
    until_dt = (
        datetime.date.fromisoformat(until) if until
        else today - datetime.timedelta(days=1)
    )

    print("  Backfilling full CD-issuance dataset (paging all snapshots) ...",
          end=" ", flush=True)
    rows = fetch_datagokr_rows(session, _SERVICE_URL, key, {}, page_size=1000)
    print(f"{len(rows)} raw rows")

    isin_rows = _dedup_by_isin(rows)
    print(f"  {len(isin_rows)} unique CDs (isinCd)")
    grouped = _flow_by_issue_date(isin_rows, since_dt, until_dt)
    stock_totals = _stock_by_bas_dt(rows, since_dt, until_dt)

    observations = _flow_observations(grouped, now) + _stock_observations(stock_totals, now)
    return indicators, observations


def main() -> int:
    return run_main(
        vendor="ksd",
        topic="cd_issuance",
        fetch_fn=run_fetch,
        description=__doc__.splitlines()[0] if __doc__ else "",
        country_code="KR",
        allow_empty=True,
    )


if __name__ == "__main__":
    import sys
    sys.exit(main())
