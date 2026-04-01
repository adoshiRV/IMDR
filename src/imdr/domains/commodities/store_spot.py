"""Parquet store for commodity spot prices.

Layout: data/parquet/commodities/fact_spot/{YYYY-MM}.parquet
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import structlog

_log = structlog.get_logger("CmdtySpotParquetStore")

DATA_ROOT = Path("data/parquet/commodities/fact_spot")
NATURAL_KEY = ["spot_tag", "obs_date"]


def write(
    df: pd.DataFrame,
    data_root: Path | None = None,
    manifest: dict[str, Any] | None = None,
) -> list[Path]:
    """Write spot DataFrame to parquet, split by month."""
    root = data_root or DATA_ROOT

    if df.empty:
        return []

    written: list[Path] = []
    df = df.copy()
    df["obs_date"] = pd.to_datetime(df["ts"]).dt.date
    df["_month"] = pd.to_datetime(df["ts"]).dt.strftime("%Y-%m")

    for month, group in df.groupby("_month"):
        root.mkdir(parents=True, exist_ok=True)
        target = root / f"{month}.parquet"
        tmp = root / f"{month}.tmp.parquet"

        write_df = group[["obs_date", "spot_tag", "value"]].copy()

        if target.exists():
            existing = pd.read_parquet(target)
            write_df = pd.concat([existing, write_df], ignore_index=True)

        write_df = write_df.sort_values(NATURAL_KEY).drop_duplicates(
            subset=NATURAL_KEY, keep="last"
        ).reset_index(drop=True)

        write_df.to_parquet(tmp, index=False, engine="pyarrow")
        os.replace(str(tmp), str(target))
        written.append(target)
        _log.info("parquet_written", path=str(target), rows=len(write_df))

    if manifest:
        for month, _ in df.groupby("_month"):
            manifest_path = root / f"{month}_manifest.json"
            manifest_data = {
                **manifest,
                "month": month,
                "write_ts": datetime.now(timezone.utc).isoformat(),
            }
            with open(manifest_path, "w", encoding="utf-8") as f:
                json.dump(manifest_data, f, indent=2, default=str)

    return written
