"""KOSIS BOK Import & Export Price Indices fetcher (DT_401Y015 + DT_402Y014).

Source: Bank of Korea (orgId=301), 수입물가지수(기본분류) + 수출물가지수(기본분류)
— Import & Export Price Indices (Basic Groups), base 2020=100, monthly.

Both tables are 2-axis (C1 = item, C2 = currency basis). We pull All-items
(`*AA`) on **two currency bases** (Won and Dollar) for each table = 4 headline
indicators. Sector-level cuts (275 import items / 239 export items) are
deferred to a later round.

Indicators:
  BOK.IMPORT_PRICE.ALL.WON.KR    Import price index, All items, KRW basis
  BOK.IMPORT_PRICE.ALL.USD.KR    Import price index, All items, USD basis
  BOK.EXPORT_PRICE.ALL.WON.KR    Export price index, All items, KRW basis
  BOK.EXPORT_PRICE.ALL.USD.KR    Export price index, All items, USD basis

The Won-vs-Dollar gap on the import side is the cleanest single FX
pass-through gauge — Won basis includes the FX move, Dollar basis is
the underlying world-price move.

Cell mapping: 2.1 Input Costs → ⚠ → ✅. Also feeds 2.2 Producer Prices
(pipeline pressure).

Usage:
    C:/Users/adoshi/.conda/envs/imdr/python.exe scripts/econ/kr/kosis/kosis_trade_prices.py
    python -m scripts.econ.kr.kosis.kosis_trade_prices
"""

from __future__ import annotations

import datetime

from imdr.domains.econ.kosis_http import fetch_kosis_table, make_session, parse_kosis_period
from imdr.domains.econ.schema import IndicatorRow, ObservationRow
from scripts.econ._runner import run_main

UTC = datetime.timezone.utc

# (tbl_id, kind_imdr_prefix, kind_display) — Import vs Export
_TABLES: list[tuple[str, str, str]] = [
    ("DT_401Y015", "IMPORT_PRICE", "Import Price Index"),
    ("DT_402Y014", "EXPORT_PRICE", "Export Price Index"),
]

# C2 currency-basis codes → (imdr_suffix, display)
_CURRENCY: dict[str, tuple[str, str]] = {
    "W": ("WON", "KRW basis"),
    "D": ("USD", "USD basis"),
    # "C" Contractual Currency Basis omitted — rarely used downstream
}

# Pull All-items only at this stage.
_C1_TARGET = "*AA"


def run_fetch(
    since: str | None,
    until: str | None,
) -> tuple[list[IndicatorRow], list[ObservationRow]]:
    session = make_session()
    since_dt = datetime.date.fromisoformat(since) if since else None
    until_dt = datetime.date.fromisoformat(until) if until else None
    now = datetime.datetime.now(UTC)

    indicators: list[IndicatorRow] = []
    observations: list[ObservationRow] = []

    for tbl_id, kind_prefix, kind_display in _TABLES:
        # Discovery call: 1-period × ALL items to find the full prefixed *AA code.
        # We can't pull full history with objL1=ALL × objL2=ALL — that exceeds
        # the 40k-cell cap (275 items × 3 currencies × 540 months > 40k).
        disc = fetch_kosis_table(
            session,
            org_id="301",
            tbl_id=tbl_id,
            obj_l1="ALL",
            itm_id="ALL",
            prd_se="M",
            new_est_prd_cnt=1,
            extra_params={"objL2": "ALL"},
        )
        all_items_c1 = None
        for r in disc:
            c1 = r.get("C1") or ""
            if c1.split(".")[-1] == _C1_TARGET:
                all_items_c1 = c1
                break
        if not all_items_c1:
            print(f"  WARN: could not find '*AA' in {tbl_id} discovery call")
            continue

        print(f"  Fetching {kind_display} ({tbl_id}, objL1={all_items_c1.split('.')[-1]}) ...",
              end=" ", flush=True)
        rows = fetch_kosis_table(
            session,
            org_id="301",
            tbl_id=tbl_id,
            obj_l1=all_items_c1,
            itm_id="ALL",
            prd_se="M",
            start_prd_de="198001",
            end_prd_de=datetime.date.today().strftime("%Y%m"),
            extra_params={"objL2": "ALL"},
        )
        print(f"{len(rows)} rows")

        for c2_code, (curr_suffix, curr_display) in _CURRENCY.items():
            sub = [
                r for r in rows
                if (r.get("C1") or "").split(".")[-1] == _C1_TARGET
                and (r.get("C2") or "").split(".")[-1] == c2_code
            ]
            if not sub:
                print(f"  WARN: no rows for {tbl_id} C1=*AA × C2={c2_code} ({curr_suffix})")
                continue

            imdr_code = f"BOK.{kind_prefix}.ALL.{curr_suffix}.KR"
            indicators.append(IndicatorRow(
                imdr_code=imdr_code,
                vendor_name="KOSIS",
                source_code=f"301/{tbl_id}/C1=*AA/C2={c2_code}",
                display_name=f"Korea — {kind_display}, All items ({curr_display}), 2020=100 (BOK)",
                unit="index",
                frequency="MONTHLY",
                country_iso="KR",
                category="cpi",
                is_seasonally_adjusted=False,
                bbg_ticker=None,
            ))
            for r in sub:
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
        topic="trade_prices",
        fetch_fn=run_fetch,
        description=__doc__.splitlines()[0] if __doc__ else "",
        country_code="KR",
    )


if __name__ == "__main__":
    import sys
    sys.exit(main())
