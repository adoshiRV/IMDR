"""
Hive-partitioned Parquet store for rates data.

Layout:
  data/parquet/rates/ccy={CCY}/curve={CURVE}/quote={QUOTE}/{YYYY-MM}.parquet

Each parquet file stores [ts, tenor, value]. Partition columns (ccy, curve, quote)
are reconstructed from the directory path. Monthly files are a write-side optimization.

Features:
  - Atomic writes via temp file + os.replace()
  - Dedup with keep='last' (newer fetches overwrite older values)
  - Manifest JSON alongside data for gap detection
  - Optional benchmark annotation on read

Ported from RATES_data/src/store.py — adapted to IMDR data/parquet/ hierarchy.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import structlog

from imdr.domains.rates.schema import COLUMNS

_log = structlog.get_logger("RatesParquetStore")

DATA_ROOT = Path("data/parquet/rates")


# ── Write ────────────────────────────────────────────────────────

def write(
    df: pd.DataFrame,
    data_root: Path | None = None,
    manifest: dict[str, Any] | None = None,
) -> list[Path]:
    """Write DataFrame to hive-partitioned parquet, split by month.

    Parameters
    ----------
    df : pd.DataFrame
        Must have columns [ts, ccy, curve, quote, tenor, value]
    data_root : Path
        Root directory. Default: data/parquet/rates/
    manifest : dict
        Optional manifest metadata to write alongside data

    Returns
    -------
    List of parquet file paths written
    """
    root = data_root or DATA_ROOT

    if df.empty:
        return []

    missing = set(COLUMNS) - set(df.columns)
    if missing:
        raise ValueError(f"Missing columns: {missing}")

    written: list[Path] = []

    df = df.copy()
    df["_month"] = df["ts"].dt.strftime("%Y-%m")

    for (ccy, curve, quote, month), group in df.groupby(["ccy", "curve", "quote", "_month"]):
        partition_dir = root / f"ccy={ccy}" / f"curve={curve}" / f"quote={quote}"
        partition_dir.mkdir(parents=True, exist_ok=True)

        target = partition_dir / f"{month}.parquet"
        tmp = partition_dir / f"{month}.tmp.parquet"

        write_df = group[["ts", "tenor", "value"]].copy()

        # Merge with existing data
        if target.exists():
            existing = pd.read_parquet(target)
            write_df = pd.concat([existing, write_df], ignore_index=True)

        # Dedup: keep last occurrence per (ts, tenor)
        write_df = write_df.sort_values(["tenor", "ts"]).drop_duplicates(
            subset=["ts", "tenor"], keep="last"
        ).reset_index(drop=True)

        write_df = write_df.sort_values(["ts", "tenor"]).reset_index(drop=True)

        # Atomic write
        write_df.to_parquet(tmp, index=False, engine="pyarrow")
        os.replace(str(tmp), str(target))

        written.append(target)
        _log.info("parquet_written", path=str(target), rows=len(write_df))

    # Write manifests
    if manifest:
        for (ccy, curve, quote, month), _ in df.groupby(["ccy", "curve", "quote", "_month"]):
            partition_dir = root / f"ccy={ccy}" / f"curve={curve}" / f"quote={quote}"
            manifest_path = partition_dir / f"{month}_manifest.json"
            manifest_data = {
                **manifest,
                "ccy": ccy,
                "curve": curve,
                "quote": quote,
                "month": month,
                "write_ts": datetime.now(timezone.utc).isoformat(),
            }
            with open(manifest_path, "w", encoding="utf-8") as f:
                json.dump(manifest_data, f, indent=2, default=str)

    return written


# ── Read ─────────────────────────────────────────────────────────

def read(
    ccy: str | None = None,
    curve: str | None = None,
    quote: str | None = None,
    tenor: str | None = None,
    start: str | None = None,
    end: str | None = None,
    annotate_benchmark: bool = False,
    data_root: Path | None = None,
) -> pd.DataFrame:
    """Read rates data from hive-partitioned parquet store.

    All parameters are optional filters. Returns full 6-column DataFrame.
    """
    root = data_root or DATA_ROOT

    if not root.exists():
        return pd.DataFrame(columns=COLUMNS)

    dirs = _find_partitions(root, ccy, curve, quote)
    if not dirs:
        return pd.DataFrame(columns=COLUMNS)

    frames = []
    for partition_dir, p_ccy, p_curve, p_quote in dirs:
        parquet_files = sorted(partition_dir.glob("*.parquet"))
        for pf in parquet_files:
            if pf.name.endswith(".tmp.parquet"):
                continue
            try:
                part_df = pd.read_parquet(pf)
            except Exception:
                continue
            part_df["ccy"] = p_ccy
            part_df["curve"] = p_curve
            part_df["quote"] = p_quote
            frames.append(part_df)

    if not frames:
        return pd.DataFrame(columns=COLUMNS)

    df = pd.concat(frames, ignore_index=True)
    df = df[COLUMNS]

    if tenor:
        df = df[df["tenor"] == tenor]
    if start:
        df = df[df["ts"] >= pd.Timestamp(start, tz="UTC")]
    if end:
        df = df[df["ts"] <= pd.Timestamp(end, tz="UTC")]

    if annotate_benchmark and not df.empty:
        df = _annotate_benchmark(df)

    return df.sort_values(["ccy", "curve", "quote", "ts", "tenor"]).reset_index(drop=True)


def _find_partitions(
    root: Path,
    ccy: str | None,
    curve: str | None,
    quote: str | None,
) -> list[tuple]:
    """Find matching partition directories."""
    results = []

    ccy_pattern = f"ccy={ccy.upper()}" if ccy else "ccy=*"
    for ccy_dir in sorted(root.glob(ccy_pattern)):
        if not ccy_dir.is_dir():
            continue
        p_ccy = ccy_dir.name.split("=", 1)[1]

        curve_pattern = f"curve={curve.upper()}" if curve else "curve=*"
        for curve_dir in sorted(ccy_dir.glob(curve_pattern)):
            if not curve_dir.is_dir():
                continue
            p_curve = curve_dir.name.split("=", 1)[1]

            quote_pattern = f"quote={quote.lower()}" if quote else "quote=*"
            for quote_dir in sorted(curve_dir.glob(quote_pattern)):
                if not quote_dir.is_dir():
                    continue
                p_quote = quote_dir.name.split("=", 1)[1]

                results.append((quote_dir, p_ccy, p_curve, p_quote))

    return results


def _annotate_benchmark(df: pd.DataFrame) -> pd.DataFrame:
    """Add curve_type and curve_status columns from universe."""
    from imdr.universe.rates import get_rates_universe

    universe = get_rates_universe()
    type_map = {}
    status_map = {}

    for _, row in df[["ccy", "curve"]].drop_duplicates().iterrows():
        key = (row["ccy"], row["curve"])
        try:
            entry = universe.get_curve(row["ccy"], row["curve"])
            type_map[key] = entry.type
            status_map[key] = entry.status
        except KeyError:
            type_map[key] = "unknown"
            status_map[key] = "unknown"

    df = df.copy()
    df["curve_type"] = df.apply(lambda r: type_map.get((r["ccy"], r["curve"]), "unknown"), axis=1)
    df["curve_status"] = df.apply(lambda r: status_map.get((r["ccy"], r["curve"]), "unknown"), axis=1)
    return df
