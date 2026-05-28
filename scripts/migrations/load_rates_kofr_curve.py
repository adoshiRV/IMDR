"""One-shot load: KRW KOFR curve (overnight + OIS 1W..5Y) into IMDR.

Reads the manual Bloomberg drop at
``Z:\\Business\\Personnel\\Arjun\\IMDR_MANUAL_UPLOADS\\May 2026\\kofr curve.xlsx``
(sheet ``value pasted``) and:

1.  Inserts ``rates.dim_curve`` row ``KRW / KOFR`` (rfr / ois /
    ``BBG:KRW-KOFR-ON`` / country_id=27 KR) if not already present.
2.  Recomputes the daily overnight KOFR rate from the cumulative
    ``KRFRINDX Index`` column using ACT/365 calendar-day spacing
    — the file's ``KOFR Rate`` column is downstream-derived without
    day-count adjustment and prints 7-20% spurious values on every
    weekend/holiday bridge.
3.  Bulk-upserts ~5,300 rows into ``rates.fact_observation`` —
    one ``1D`` row per index date and one row per ``(obs_date, tenor)``
    where the per-tenor value is non-null. No filter on Bloomberg's
    per-tenor "last-print" date (KRW KOFR swaps are illiquid;
    Bloomberg forward-fills the date but the value updates regularly).

Idempotent on ``(curve_id, vendor_id, ts, quote, tenor, frequency_id)``
— re-runs are MERGE no-ops.

Usage:
    python -m scripts.migrations.load_rates_kofr_curve              # dry-run
    python -m scripts.migrations.load_rates_kofr_curve --execute    # write
    python -m scripts.migrations.load_rates_kofr_curve --file PATH  # custom xlsx
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from sqlalchemy import select

from imdr.config.settings import get_settings
from imdr.connectors.mssql import MSSQLConnector
from imdr.domains.rates.repository import (
    RatesCurveRepository,
    RatesObservationRepository,
)
from imdr.models.country import DimCountry
from imdr.models.rates import RatesCurve
from imdr.schemas.rates import RatesObservationCreate


DEFAULT_FILE = Path(
    r"Z:\Business\Personnel\Arjun\IMDR_MANUAL_UPLOADS\May 2026\kofr curve.xlsx"
)
SHEET = "value pasted"

# Column layout — pairs of (date_col, value_col) starting at col 3.
# Each tenor's BBG ticker and value live at adjacent columns.
TENOR_LAYOUT: list[tuple[str, str, int]] = [
    # (tenor, ticker, value_col_index)  — date_col = value_col - 1
    ("1W",  "KWKON1Z",  4),
    ("2W",  "KWKON2Z",  6),
    ("3W",  "KWKON3Z",  8),
    ("1M",  "KWKONA",  10),
    ("2M",  "KWKONB",  12),
    ("3M",  "KWKONC",  14),
    ("6M",  "KWKONF",  16),
    ("9M",  "KWKONI",  18),
    ("1Y",  "KWKON1",  20),
    ("18M", "KWKON1F", 22),
    ("2Y",  "KWKON2",  24),
    ("3Y",  "KWKON3",  26),
    ("4Y",  "KWKON4",  28),
    ("5Y",  "KWKON5",  30),
]

CCY = "KRW"
CURVE = "KOFR"
COUNTRY_CODE = "KR"
CITI_PREFIX = "BBG:KRW-KOFR-ON"
VENDOR_CODE = "BBG"
FREQUENCY_CODE = "DAILY"
QUOTE = "par"


def _build_overnight_rows(df: pd.DataFrame) -> pd.DataFrame:
    """Recompute O/N rate from KOFR Index using ACT/365 calendar-day spacing."""
    s = pd.DataFrame({
        "obs_date": pd.to_datetime(df.iloc[:, 0]),
        "index":    pd.to_numeric(df.iloc[:, 1], errors="coerce"),
    }).dropna(subset=["obs_date", "index"]).sort_values("obs_date").reset_index(drop=True)

    s["days_gap"] = s["obs_date"].diff().dt.days
    s["value"] = (s["index"] / s["index"].shift(1) - 1) * 365 / s["days_gap"] * 100
    s["tenor"] = "1D"
    out = s.dropna(subset=["value"])[["obs_date", "tenor", "value"]]
    return out


def _build_swap_rows(df: pd.DataFrame) -> pd.DataFrame:
    """One row per (obs_date, tenor) where value is non-null."""
    obs_date = pd.to_datetime(df.iloc[:, 0])
    chunks: list[pd.DataFrame] = []
    for tenor, _ticker, val_col in TENOR_LAYOUT:
        vals = pd.to_numeric(df.iloc[:, val_col], errors="coerce")
        chunk = pd.DataFrame({"obs_date": obs_date, "tenor": tenor, "value": vals})
        chunks.append(chunk.dropna(subset=["obs_date", "value"]))
    return pd.concat(chunks, ignore_index=True)


def _coverage_report(on_df: pd.DataFrame, swap_df: pd.DataFrame) -> None:
    print(f"  Overnight (1D, recomputed from index): {len(on_df):,} rows", flush=True)
    print(f"  Date range: {on_df['obs_date'].min().date()} -> {on_df['obs_date'].max().date()}", flush=True)
    print(f"  Value range: min={on_df['value'].min():.3f}  max={on_df['value'].max():.3f}", flush=True)
    print()
    print("  Per-tenor swap coverage:", flush=True)
    by_tenor = (
        swap_df.groupby("tenor")
        .agg(rows=("value", "size"),
             min_val=("value", "min"),
             max_val=("value", "max"),
             min_date=("obs_date", "min"),
             max_date=("obs_date", "max"))
        .reindex([t for t, _, _ in TENOR_LAYOUT])
    )
    by_tenor["min_date"] = by_tenor["min_date"].dt.strftime("%Y-%m-%d")
    by_tenor["max_date"] = by_tenor["max_date"].dt.strftime("%Y-%m-%d")
    print(by_tenor.to_string(), flush=True)


def _resolve_country_id(session, country_code: str) -> int:
    row = session.execute(
        select(DimCountry).where(DimCountry.country_code == country_code)
    ).scalar_one()
    return row.id


def _resolve_vendor_id(session, vendor_code: str) -> int:
    from imdr.models.vendor import DimVendor
    row = session.execute(
        select(DimVendor).where(DimVendor.vendor_code == vendor_code)
    ).scalar_one()
    return row.id


def _resolve_frequency_id(session, frequency_code: str) -> int:
    from imdr.models.frequency import DimFrequency
    row = session.execute(
        select(DimFrequency).where(DimFrequency.frequency_code == frequency_code)
    ).scalar_one()
    return row.id


def _ensure_kofr_curve(session, country_id: int) -> RatesCurve:
    """Idempotently insert the KRW KOFR dim_curve row."""
    repo = RatesCurveRepository(session)
    existing = repo.get_by_key(CCY, CURVE)
    if existing:
        return existing
    row = RatesCurve(
        ccy=CCY,
        curve=CURVE,
        curve_type="rfr",
        curve_status="active",
        instrument="ois",
        citi_prefix=CITI_PREFIX,
        country_id=country_id,
        notes=(
            "Korean overnight unsecured RFR + OIS swap curve. O/N recomputed "
            "from KRFRINDX Index using ACT/365 calendar-day spacing; the "
            "vendor-published 'KOFR Rate' column is downstream-derived "
            "without day-count adjustment and is wrong on every "
            "weekend/holiday bridge."
        ),
    )
    session.add(row)
    session.flush()
    return row


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--execute", action="store_true",
                   help="Write to DB (default: dry-run report only)")
    p.add_argument("--file", type=Path, default=DEFAULT_FILE,
                   help=f"Excel file path (default: {DEFAULT_FILE})")
    args = p.parse_args()

    print("=" * 100, flush=True)
    print(f"KRW KOFR curve load — {'EXECUTE' if args.execute else 'DRY-RUN'}", flush=True)
    print(f"Source: {args.file}", flush=True)
    print(f"Sheet:  {SHEET}", flush=True)
    print("=" * 100, flush=True)

    if not args.file.exists():
        print(f"[!] File not found: {args.file}", flush=True)
        return 1

    print("\nReading Excel...", flush=True)
    raw = pd.read_excel(args.file, sheet_name=SHEET, header=None)
    # First two rows are header (BBG ticker + friendly label); data starts at row 2.
    df = raw.iloc[2:].reset_index(drop=True)
    print(f"  Raw data rows: {len(df)}", flush=True)

    print("\nBuilding overnight series (recomputed from index)...", flush=True)
    on_df = _build_overnight_rows(df)
    print("\nBuilding swap-tenor rows...", flush=True)
    swap_df = _build_swap_rows(df)

    print("\n" + "=" * 100, flush=True)
    print("COVERAGE REPORT", flush=True)
    print("=" * 100, flush=True)
    _coverage_report(on_df, swap_df)

    total = len(on_df) + len(swap_df)
    print()
    print(f"GRAND TOTAL: {total:,} rows ({len(on_df):,} O/N + {len(swap_df):,} swap)", flush=True)
    print("=" * 100, flush=True)

    if not args.execute:
        print("\nDRY-RUN ONLY — no DB writes.", flush=True)
        print("Re-run with --execute to insert/upsert.", flush=True)
        return 0

    # ── Real run ─────────────────────────────────────────────────────────
    settings = get_settings()
    if settings.mssql_database != "IMDR":
        raise RuntimeError(
            f"Refusing to run: IMDR_MSSQL_DATABASE={settings.mssql_database!r} "
            "(this loader only writes to the IMDR database)"
        )
    connector = MSSQLConnector(settings)

    try:
        with connector.session() as session:
            country_id = _resolve_country_id(session, COUNTRY_CODE)
            vendor_id = _resolve_vendor_id(session, VENDOR_CODE)
            frequency_id = _resolve_frequency_id(session, FREQUENCY_CODE)
            print(f"\nResolved FKs: country_id={country_id} ({COUNTRY_CODE})  "
                  f"vendor_id={vendor_id} ({VENDOR_CODE})  "
                  f"frequency_id={frequency_id} ({FREQUENCY_CODE})", flush=True)

            curve = _ensure_kofr_curve(session, country_id)
            print(f"dim_curve: KRW/KOFR curve_id={curve.id}", flush=True)

            print("\nBuilding RatesObservationCreate payload...", flush=True)
            items: list[RatesObservationCreate] = []
            for src in (on_df, swap_df):
                for row in src.itertuples(index=False):
                    ts = pd.Timestamp(row.obs_date).to_pydatetime().replace(
                        hour=0, minute=0, second=0, microsecond=0,
                        tzinfo=timezone.utc,
                    )
                    items.append(RatesObservationCreate(
                        curve_id=curve.id,
                        vendor_id=vendor_id,
                        ts=ts,
                        quote=QUOTE,
                        tenor=row.tenor,
                        value=float(row.value),
                        frequency_id=frequency_id,
                    ))
            print(f"  Built {len(items):,} observations", flush=True)

            print("\nWriting to rates.fact_observation (idempotent MERGE)...", flush=True)
            obs_repo = RatesObservationRepository(session)
            n_upserted = obs_repo.bulk_upsert(items)
            print(f"\nDONE — {n_upserted:,} rows upserted.", flush=True)
    finally:
        connector.dispose()

    return 0


if __name__ == "__main__":
    sys.exit(main())
