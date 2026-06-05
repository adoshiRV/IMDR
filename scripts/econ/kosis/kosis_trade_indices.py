"""KOSIS BOK Trade Value + Volume Indices fetcher (DT_403Y001-004).

Source: Bank of Korea (orgId=301), 4 sister tables — Trade indices,
base 2020=100, monthly:
  DT_403Y001  수출금액지수  Export Value Index
  DT_403Y002  수출물량지수  Export Volume Index
  DT_403Y003  수입금액지수  Import Value Index
  DT_403Y004  수입물량지수  Import Volume Index

Each is single-axis with hundreds of item-level cuts; we pull only
the All-items (`*AA`) row via discovery-first + per-cut filter (same
pattern as PPI / trade prices fetchers).

Cell mapping: 1.3 External Demand → ⚠ → ✅. The KOSIS-side picture
complements the BOK BoP-basis goods trade in USD-mn already loaded.
The Volume Index is the cleanest gauge of real export demand (strips
out the price moves already captured in BOK.EXPORT_PRICE.*).

Usage:
    C:/Users/adoshi/.conda/envs/imdr/python.exe scripts/econ/kosis/kosis_trade_indices.py
    python -m scripts.econ.kosis.kosis_trade_indices
"""

from __future__ import annotations

import datetime

from imdr.domains.econ.kosis_http import fetch_kosis_table, make_session, parse_kosis_period
from imdr.domains.econ.schema import IndicatorRow, ObservationRow
from scripts.econ._runner import run_main

UTC = datetime.timezone.utc

# (tbl_id, imdr_suffix, display)
_TABLES: list[tuple[str, str, str]] = [
    ("DT_403Y001", "EXPORT_VALUE",   "Export Value Index"),
    ("DT_403Y002", "EXPORT_VOLUME",  "Export Volume Index"),
    ("DT_403Y003", "IMPORT_VALUE",   "Import Value Index"),
    ("DT_403Y004", "IMPORT_VOLUME",  "Import Volume Index"),
]

_C1_TARGET = "*AA"  # All items


def _discover_full_c1(session, tbl_id: str) -> str | None:
    rows = fetch_kosis_table(
        session,
        org_id="301",
        tbl_id=tbl_id,
        obj_l1="ALL",
        itm_id="ALL",
        prd_se="M",
        new_est_prd_cnt=1,
    )
    for r in rows:
        c1 = r.get("C1") or ""
        if c1.split(".")[-1] == _C1_TARGET:
            return c1
    return None


def run_fetch(
    since: str | None,
    until: str | None,
) -> tuple[list[IndicatorRow], list[ObservationRow]]:
    session = make_session()
    since_dt = datetime.date.fromisoformat(since) if since else None
    until_dt = datetime.date.fromisoformat(until) if until else None
    now = datetime.datetime.now(UTC)
    today = datetime.date.today()

    indicators: list[IndicatorRow] = []
    observations: list[ObservationRow] = []

    for tbl_id, imdr_suffix, display in _TABLES:
        full_c1 = _discover_full_c1(session, tbl_id)
        if not full_c1:
            print(f"  WARN: '*AA' not found in {tbl_id}")
            continue
        print(f"  Fetching {tbl_id} ({display}) ...", end=" ", flush=True)
        rows = fetch_kosis_table(
            session,
            org_id="301",
            tbl_id=tbl_id,
            obj_l1=full_c1,
            itm_id="ALL",
            prd_se="M",
            start_prd_de="198001",
            end_prd_de=today.strftime("%Y%m"),
        )
        print(f"{len(rows)} rows")

        imdr_code = f"BOK.TRADE.{imdr_suffix}.KR"
        indicators.append(IndicatorRow(
            imdr_code=imdr_code,
            vendor_name="KOSIS",
            source_code=f"301/{tbl_id}/C1=*AA",
            display_name=f"Korea — {display}, All items, 2020=100 (BOK monthly)",
            unit="index",
            frequency="MONTHLY",
            country_iso="KR",
            category="bop",
            is_seasonally_adjusted=False,
            bbg_ticker=None,
        ))
        for r in rows:
            ymd = parse_kosis_period(r.get("PRD_DE"), "M")
            if ymd is None:
                continue
            obs_date = datetime.date(*ymd)
            if since_dt and obs_date < since_dt:
                continue
            if until_dt and obs_date > until_dt:
                continue
            try:
                value = float(r["DT"]) if r.get("DT") not in (None, "") else None
            except (TypeError, ValueError):
                value = None
            observations.append(ObservationRow(
                imdr_code=imdr_code,
                obs_date=obs_date,
                vintage=0,
                release_date=now,
                value=value,
                ingested_at=now,
            ))

    return indicators, observations


def main() -> int:
    return run_main(
        vendor="kosis",
        topic="trade_indices",
        fetch_fn=run_fetch,
        description=__doc__.splitlines()[0] if __doc__ else "",
    )


if __name__ == "__main__":
    import sys
    sys.exit(main())
