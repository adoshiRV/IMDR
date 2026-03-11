"""Hive-partitioned Parquet store for FX vol data.

Layout:
  data/parquet/fx/fact_vol/{base}_{quote}/{YYYY-MM}.parquet

Each parquet file stores [obs_date, strike, tenor, vol_type, value].
Partition columns (base_ccy, quote_ccy) are reconstructed from the directory path.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import structlog

from imdr.domains.fx.vol_translate import COLUMNS

_log = structlog.get_logger("FXVolParquetStore")

DATA_ROOT = Path("data/parquet/fx/fact_vol")


def write(
    df: pd.DataFrame,
    data_root: Path | None = None,
    manifest: dict[str, Any] | None = None,
) -> list[Path]:
    """Write vol DataFrame to hive-partitioned parquet, split by pair + month.

    Parameters
    ----------
    df : pd.DataFrame
        Must have columns [ts, base_ccy, quote_ccy, strike, tenor, vol_type, value]
    data_root : Path
        Root directory. Default: data/parquet/fx/fact_vol/
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
    df["obs_date"] = pd.to_datetime(df["ts"]).dt.date
    df["_month"] = pd.to_datetime(df["ts"]).dt.strftime("%Y-%m")

    for (base_ccy, quote_ccy, month), group in df.groupby(["base_ccy", "quote_ccy", "_month"]):
        partition_dir = root / f"{base_ccy}_{quote_ccy}"
        partition_dir.mkdir(parents=True, exist_ok=True)

        target = partition_dir / f"{month}.parquet"
        tmp = partition_dir / f"{month}.tmp.parquet"

        write_df = group[["obs_date", "strike", "tenor", "vol_type", "value"]].copy()

        # Merge with existing data
        if target.exists():
            existing = pd.read_parquet(target)
            write_df = pd.concat([existing, write_df], ignore_index=True)

        # Dedup: keep last occurrence per natural key
        write_df = write_df.sort_values(
            ["obs_date", "strike", "tenor", "vol_type"]
        ).drop_duplicates(
            subset=["obs_date", "strike", "tenor", "vol_type"], keep="last"
        ).reset_index(drop=True)

        # Atomic write
        write_df.to_parquet(tmp, index=False, engine="pyarrow")
        os.replace(str(tmp), str(target))

        written.append(target)
        _log.info("parquet_written", path=str(target), rows=len(write_df))

    # Write manifests
    if manifest:
        for (base_ccy, quote_ccy, month), _ in df.groupby(["base_ccy", "quote_ccy", "_month"]):
            partition_dir = root / f"{base_ccy}_{quote_ccy}"
            manifest_path = partition_dir / f"{month}_manifest.json"
            manifest_data = {
                **manifest,
                "base_ccy": base_ccy,
                "quote_ccy": quote_ccy,
                "month": month,
                "write_ts": datetime.now(timezone.utc).isoformat(),
            }
            with open(manifest_path, "w", encoding="utf-8") as f:
                json.dump(manifest_data, f, indent=2, default=str)

    return written
