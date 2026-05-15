"""FX OHLC pipeline — extract → validate → DB → parquet for a single hour.

`process_hour()` is the shared core, called once by the live script and in a
loop by the historical script. `FXOHLCPipeline` is a `BasePipeline` wrapper
that adds an audit trail when invoked via `run_pipeline.py`.

Target table: [FX].[fact_ohlc]
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import structlog

from imdr.config.pipeline_config import get_pipeline_config
from imdr.config.settings import Settings
from imdr.connectors.mssql import MSSQLConnector
from imdr.connectors.reader import AnalyticalReader
from imdr.domains.fx.extractors_ohlc import BidFXExtractor, PairCache
from imdr.domains.fx.repository_ohlc import FXOHLCRepository
from imdr.healthchecks.base import CheckStatus
from imdr.healthchecks.quality import (
    ColumnOrderCheck,
    PercentageChangeCheck,
    PositiveValueCheck,
    RobustStatisticalOutlierCheck,
    SymbolRangeCheck,
)
from imdr.pipelines.base import BasePipeline
from imdr.reporting.run_report import RunReport
from imdr.schemas.fx_ohlc import FXFactOHLCCreate
from imdr.universe.fx import FXUniverse
from imdr.utils.time_windows import HourWindow

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
    currencies: set[str] | None = None,
) -> HourResult:
    """Process a single hour: fetch ticks -> build bars -> validate -> write DB -> parquet.

    This is the shared core. Live calls it once. Historical calls it in a loop.
    When *currencies* is provided, only those currencies are fetched (cleanup mode).
    """
    result = HourResult(window=window)
    # Cleaning thresholds for post-ingest quality checks come from pipelines.yml
    # (previously hardcoded as 5.0 / 4.0 / 12 — diverged from the configured
    # `fx.ohlc.cleaning` section which the batch cleaner already honoured).
    cleaning = get_pipeline_config("fx.ohlc").cleaning

    # 1. Extract: fetch ticks and build bars
    extractor = BidFXExtractor(
        settings=settings,
        universe=universe,
        window=window,
        pair_cache=pair_cache,
        currencies=currencies,
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
    if currencies is not None:
        expected_symbols = {
            sym for sym in universe.api_symbols()
            if universe.currency_from_symbol(sym) in currencies
        }
    else:
        expected_symbols = set(universe.api_symbols())
    produced_symbols = {bar["symbol"] for bar in bars}
    result.missing_ccy = sorted(expected_symbols - produced_symbols)
    if result.missing_ccy:
        report.warning("missing_ccy", f"Missing {len(result.missing_ccy)} symbols", details={
            "missing": result.missing_ccy,
        })

    # 4. Anomaly pre-screen (compare close_px to previous hour, batched)
    anomalies = _anomaly_prescreen(validated, connector, settings.anomaly_pct_threshold)
    result.anomalies = anomalies
    # (anomaly_pct_threshold is the *live* anomaly trigger; the cleaning
    # `pct_threshold` is for the batch sweeper. They are distinct on purpose.)
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
        quality_flags = _post_ingest_quality(connector, window, universe, cleaning, report)
        result.quality_flags = quality_flags

    # 7. Write Parquet archive
    if approved and settings.parquet_batch_dir:
        parquet_error = _write_parquet(approved, window, settings.parquet_batch_dir)
        if parquet_error is None:
            report.info("parquet", f"Archived {len(approved)} bars to parquet")
        else:
            # Surface the failure in the run record instead of just a log line.
            result.diagnostics.append(parquet_error)
            report.warning(
                "parquet",
                f"Parquet archive failed: {parquet_error['error']}",
                details=parquet_error,
            )

    return result


_PRICE_COLS = [
    "open_px", "high_px", "low_px", "close_px",
    "mid_px", "mid_mean_px", "mid_median_px", "bid", "ask",
]


def _build_quality_checks(universe: FXUniverse, cleaning) -> list:
    """Build the post-ingest quality check list.

    Thresholds (``n_mad``, ``trailing_months``, ``pct_threshold``) come from
    the ``fx.ohlc.cleaning`` section of pipelines.yml so post-ingest checks
    and the batch cleaner stay in sync. ``pct_threshold`` falls back to 5.0
    when omitted from config.
    """
    pct_threshold = cleaning.pct_threshold if cleaning.pct_threshold is not None else 5.0
    checks: list = [
        PositiveValueCheck(columns=_PRICE_COLS),
        ColumnOrderCheck(rules=[("bid", "<=", "ask")]),
        PercentageChangeCheck(
            value_column="close_px",
            threshold_pct=pct_threshold,
        ),
        SymbolRangeCheck(
            ranges={
                sym: (r.min, r.max)
                for sym in universe.expected_ranges
                if (r := universe.expected_range_for(sym)) is not None
            },
            value_column="close_px",
        ),
        RobustStatisticalOutlierCheck(
            value_column="close_px",
            group_columns=["symbol", "series"],
            n_mad=cleaning.n_mad,
            trailing_months=cleaning.trailing_months,
        ),
    ]
    return checks


def _post_ingest_quality(
    connector: MSSQLConnector,
    window: HourWindow,
    universe: FXUniverse,
    cleaning,
    report: RunReport,
) -> list[dict[str, Any]]:
    """Run quality checks on the just-ingested hour and return flags."""
    flags: list[dict[str, Any]] = []
    reader = AnalyticalReader(connector)
    table = "[fx].[fact_ohlc]"
    # Scope checks to this hour
    where = f"AND [ts] = '{window.start:%Y-%m-%d %H:%M:%S}'"

    for check in _build_quality_checks(universe, cleaning):
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
    """Compare each bar's close_px against the previous hour's close.

    Uses `get_last_closes_batch()` — one query for all (symbol, series)
    pairs in the hour, vs the previous per-bar lookup which was N+1.
    """
    anomalies: list[dict[str, Any]] = []
    if not bars:
        return anomalies

    # All bars in a single hour share the same `ts`; pull one lookup for them.
    before_ts = bars[0].ts
    keys = list({(bar.symbol, bar.series) for bar in bars})

    with connector.session() as session:
        repo = FXOHLCRepository(session)
        prev_by_key = repo.get_last_closes_batch(keys, before_ts)

    for bar in bars:
        prev = prev_by_key.get((bar.symbol, bar.series))
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
) -> dict[str, Any] | None:
    """Archive approved bars to a Parquet file.

    Returns ``None`` on success, or a diagnostic dict on failure so the
    orchestrator can surface the issue in the run record. Previously the
    `except` swallowed silently — a parquet write failure produced only a
    log line with no fingerprint in the audit trail.
    """
    try:
        import pandas as pd

        records = [b.model_dump() for b in bars]
        df = pd.DataFrame(records)
        path = Path(batch_dir) / "fx" / "fact_ohlc" / f"{window.start:%Y}" / f"{window.start:%m}" / f"{window.start:%d}" / f"fx_ohlc_{window.start:%Y%m%d_%H%M}.parquet"
        path.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(path, index=False)
        return None
    except Exception as exc:
        log.exception("parquet_write_failed")
        return {
            "step": "parquet",
            "error": f"{type(exc).__name__}: {exc}",
            "batch_dir": str(batch_dir),
            "window": str(window),
        }


class FXOHLCPipeline(BasePipeline[None, None, HourResult]):
    """FX OHLC bar ingestion pipeline.

    Delegates to `process_hour()` for the actual work; adds `BasePipeline`'s
    audit trail and health check integration when invoked via `run_pipeline.py`.
    """

    pipeline_name = "fx.ohlc"
    domain = "fx"

    def __init__(
        self,
        connector: MSSQLConnector,
        settings: Settings,
        universe: FXUniverse,
        window: HourWindow,
        report: RunReport | None = None,
        pair_cache: PairCache | None = None,
    ) -> None:
        super().__init__(connector)
        self._settings = settings
        self._universe = universe
        self._window = window
        self._report = report or RunReport(pipeline_name=self.pipeline_name)
        self._pair_cache = pair_cache
        self._result: HourResult | None = None

    def extract(self) -> None:
        # All work delegated to process_hour() in load()
        return None

    def transform(self, raw: None) -> None:
        return None

    def load(self, data: None) -> HourResult:
        # process_hour handles extract + transform + validate + load + parquet
        result = process_hour(
            window=self._window,
            universe=self._universe,
            settings=self._settings,
            connector=self._connector,
            report=self._report,
            pair_cache=self._pair_cache,
        )
        self._result = result
        return result

    def get_run_context(self) -> dict[str, Any]:
        return {
            "run_date": self._window.start.date(),
            "window": str(self._window),
        }
