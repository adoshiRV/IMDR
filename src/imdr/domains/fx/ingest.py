"""Shared FX OHLC ingest logic — process_hour() is the core function.

Used by both live (single hour) and historical (loop of hours) scripts.
This avoids code duplication between scripts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import structlog

from imdr.config.settings import Settings
from imdr.connectors.mssql import MSSQLConnector
from imdr.connectors.reader import AnalyticalReader
from imdr.domains.fx.extractors import BidFXExtractor, PairCache
from imdr.domains.fx.repository import FXOHLCRepository
from imdr.domains.fx.time_utils import HourWindow
from imdr.healthchecks.base import CheckStatus
from imdr.healthchecks.quality import (
    ColumnOrderCheck,
    PositiveValueCheck,
    RobustStatisticalOutlierCheck,
)
from imdr.reporting.run_report import RunReport
from imdr.schemas.fx_ohlc import FXFactOHLCCreate
from imdr.universe.fx import FXUniverse

log = structlog.get_logger(__name__)


@dataclass
class HourResult:
    """Result of processing a single hour."""

    window: HourWindow
    bars_produced: int = 0
    bars_approved: int = 0
    bars_dropped: int = 0
    bars: list[dict[str, Any]] = field(default_factory=list)
    diagnostics: list[dict[str, Any]] = field(default_factory=list)
    missing_ccy: list[str] = field(default_factory=list)
    anomalies: list[dict[str, Any]] = field(default_factory=list)
    quality_flags: list[dict[str, Any]] = field(default_factory=list)


def process_hour(
    window: HourWindow,
    universe: FXUniverse,
    settings: Settings,
    connector: MSSQLConnector,
    report: RunReport,
    pair_cache: PairCache | None = None,
) -> HourResult:
    """Process a single hour: fetch ticks -> build bars -> validate -> write DB -> parquet.

    This is the shared core. Live calls it once. Historical calls it in a loop.
    """
    result = HourResult(window=window)

    # 1. Extract: fetch ticks and build bars
    extractor = BidFXExtractor(
        settings=settings,
        universe=universe,
        window=window,
        pair_cache=pair_cache,
    )
    bars = extractor.extract()
    result.bars = bars
    result.bars_produced = len(bars)
    result.diagnostics = [
        {"symbol": d.symbol, "series": d.series, "reason": d.reason}
        for d in extractor.diagnostics if not d.success
    ]

    report.info("extract", f"Produced {len(bars)} bars for {window}", details={
        "window": str(window),
        "bars_produced": len(bars),
        "drops": len(result.diagnostics),
    })

    if not bars:
        report.warning("extract", f"No bars produced for {window}")
        return result

    # 2. Validate: Pydantic validation
    validated: list[FXFactOHLCCreate] = []
    for bar in bars:
        try:
            validated.append(FXFactOHLCCreate.model_validate(bar))
        except Exception as exc:
            report.warning("validation", f"Bar validation failed: {exc}", details=bar)

    # 3. Check for missing currencies
    expected_symbols = set(universe.api_symbols())
    produced_symbols = {bar["symbol"] for bar in bars}
    result.missing_ccy = sorted(expected_symbols - produced_symbols)
    if result.missing_ccy:
        report.warning("missing_ccy", f"Missing {len(result.missing_ccy)} symbols", details={
            "missing": result.missing_ccy,
        })

    # 4. Anomaly pre-screen (compare close_px to previous hour)
    anomalies = _anomaly_prescreen(validated, connector, settings.anomaly_pct_threshold)
    result.anomalies = anomalies
    if anomalies:
        report.warning("anomaly", f"Detected {len(anomalies)} anomalies", details={
            "anomalies": anomalies,
        })

    # Approved = all validated bars (anomalies are flagged but not dropped)
    approved = validated
    result.bars_approved = len(approved)
    result.bars_dropped = result.bars_produced - result.bars_approved

    # 5. Write to MSSQL
    if approved:
        with connector.session() as session:
            repo = FXOHLCRepository(session)
            repo.bulk_upsert(approved)
        report.info("load", f"Wrote {len(approved)} bars to DB", details={
            "bars_written": len(approved),
        })

    # 6. Post-ingest quality check (robust outlier + invariant checks)
    if approved:
        quality_flags = _post_ingest_quality(connector, window, report)
        result.quality_flags = quality_flags

    # 7. Write Parquet archive
    if approved and settings.parquet_batch_dir:
        _write_parquet(approved, window, settings.parquet_batch_dir)
        report.info("parquet", f"Archived {len(approved)} bars to parquet")

    return result


_PRICE_COLS = [
    "open_px", "high_px", "low_px", "close_px",
    "mid_px", "mid_mean_px", "mid_median_px", "bid", "ask",
]

_QUALITY_CHECKS = [
    PositiveValueCheck(columns=_PRICE_COLS),
    ColumnOrderCheck(rules=[("bid", "<=", "ask")]),
    RobustStatisticalOutlierCheck(
        value_column="close_px",
        group_columns=["symbol", "series"],
        n_mad=4.0,
        trailing_months=12,
    ),
]


def _post_ingest_quality(
    connector: MSSQLConnector,
    window: HourWindow,
    report: RunReport,
) -> list[dict[str, Any]]:
    """Run quality checks on the just-ingested hour and return flags."""
    flags: list[dict[str, Any]] = []
    reader = AnalyticalReader(connector)
    table = "[fx].[fact_ohlc]"
    # Scope checks to this hour
    where = f"AND [ts] = '{window.start:%Y-%m-%d %H:%M:%S}'"

    for check in _QUALITY_CHECKS:
        try:
            result = check.run(reader, table, where=where)
            if result.status != CheckStatus.PASSED:
                flag = {
                    "check": result.check_name,
                    "status": result.status.value,
                    "message": result.message,
                }
                if result.flagged is not None and not result.flagged.empty:
                    flag["flagged_count"] = len(result.flagged)
                flags.append(flag)
                report.warning("quality", result.message, details=flag)
        except Exception as exc:
            log.warning("quality_check_failed", check=type(check).__name__, error=str(exc))

    if not flags:
        report.info("quality", "All post-ingest quality checks passed")

    return flags


def _anomaly_prescreen(
    bars: list[FXFactOHLCCreate],
    connector: MSSQLConnector,
    threshold_pct: float,
) -> list[dict[str, Any]]:
    """Compare each bar's close_px against the previous hour's close."""
    anomalies: list[dict[str, Any]] = []

    with connector.session() as session:
        repo = FXOHLCRepository(session)
        for bar in bars:
            prev = repo.get_last_close(bar.symbol, bar.series, bar.ts)
            if prev is None:
                continue
            prev_close = float(prev.close_px)
            curr_close = float(bar.close_px)
            if prev_close == 0:
                continue
            pct_change = abs((curr_close - prev_close) / prev_close) * 100
            if pct_change >= threshold_pct:
                anomalies.append({
                    "symbol": bar.symbol,
                    "series": bar.series,
                    "field": "close_px",
                    "previous": prev_close,
                    "current": curr_close,
                    "pct_change": pct_change,
                })

    return anomalies


def _write_parquet(
    bars: list[FXFactOHLCCreate],
    window: HourWindow,
    batch_dir: str,
) -> None:
    """Archive approved bars to a Parquet file."""
    try:
        import pandas as pd

        records = [b.model_dump() for b in bars]
        df = pd.DataFrame(records)
        path = Path(batch_dir) / "fx" / "fact_ohlc" / f"{window.start:%Y}" / f"{window.start:%m}" / f"{window.start:%d}" / f"fx_ohlc_{window.start:%Y%m%d_%H%M}.parquet"
        path.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(path, index=False)
    except Exception:
        log.exception("parquet_write_failed")
