"""Cross-domain data staleness monitor.

Queries every fact table in IMDR at the *per-key* level (per-curve,
per-pair, per-commodity, per-index) and flags any key whose latest
observation is older than its configured threshold.

This module is domain-agnostic — each domain registers a StalenessSpec
that describes how to query its table and what constitutes a stale key.
The monitor runs all specs and returns a unified StalenessReport.

Usage:
    from imdr.connectors.mssql import MSSQLConnector
    from imdr.healthchecks.staleness import StalenessMonitor

    connector = MSSQLConnector(settings)
    monitor = StalenessMonitor.from_config(connector)
    report = monitor.run()

    if report.has_stale:
        # send alert...
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Any

import pandas as pd
import structlog

from imdr.connectors.mssql import MSSQLConnector
from imdr.connectors.reader import AnalyticalReader

log = structlog.get_logger(__name__)


@dataclass(frozen=True)
class StalenessSpec:
    """Describes how to check staleness for one domain table.

    Attributes:
        domain:         Human label (e.g. "FX Vol").
        pipeline_name:  Matches pipelines.yml key (e.g. "fx.vol").
        table:          Fully-qualified SQL table, e.g. "[fx].[fact_vol]".
        date_column:    The observation-date column to check (e.g. "obs_date").
        key_column:     The foreign-key column that identifies a series
                        (e.g. "pair_id", "curve_id", "commodity_id").
        dim_table:      Optional dimension table for human-readable labels.
        dim_join_col:   Column in dim_table to join on (matches key_column).
        dim_label_cols: Columns from dim_table to show in reports.
        max_stale_days: How many calendar days behind today before a key
                        is flagged stale.
    """

    domain: str
    pipeline_name: str
    table: str
    date_column: str
    key_column: str
    dim_table: str | None = None
    dim_join_col: str = "id"
    dim_label_cols: tuple[str, ...] = ()
    max_stale_days: int = 3


@dataclass
class StaleKey:
    """One key (series/pair/commodity) that is behind."""

    domain: str
    pipeline_name: str
    key_id: Any
    label: str
    latest_date: date
    days_behind: int
    max_stale_days: int


@dataclass
class DomainSummary:
    """Staleness summary for one domain."""

    domain: str
    pipeline_name: str
    total_keys: int
    stale_keys: int
    fresh_keys: int
    latest_date: date | None
    stale_items: list[StaleKey] = field(default_factory=list)

    @property
    def is_stale(self) -> bool:
        return self.stale_keys > 0


@dataclass
class StalenessReport:
    """Aggregated staleness results across all domains."""

    checked_at: datetime
    reference_date: date
    summaries: list[DomainSummary] = field(default_factory=list)

    @property
    def has_stale(self) -> bool:
        return any(s.is_stale for s in self.summaries)

    @property
    def total_stale_keys(self) -> int:
        return sum(s.stale_keys for s in self.summaries)

    @property
    def stale_domains(self) -> list[DomainSummary]:
        return [s for s in self.summaries if s.is_stale]

    @property
    def healthy_domains(self) -> list[DomainSummary]:
        return [s for s in self.summaries if not s.is_stale]

    def all_stale_keys(self) -> list[StaleKey]:
        """Flat list of all stale keys across domains, sorted worst-first."""
        keys: list[StaleKey] = []
        for s in self.summaries:
            keys.extend(s.stale_items)
        keys.sort(key=lambda k: k.days_behind, reverse=True)
        return keys


# ── Default specs for all IMDR domains ────────────────────────────────

# These match the current schema.  When new domains are added, add a
# spec here.

DEFAULT_SPECS: list[StalenessSpec] = [
    # ── Rates ──────────────────────────────────────────────────────
    StalenessSpec(
        domain="Rates Curves",
        pipeline_name="rates.historical",
        table="[rates].[fact_observation]",
        date_column="ts",
        key_column="curve_id",
        dim_table="[rates].[dim_curve]",
        dim_join_col="id",
        dim_label_cols=("ccy", "curve"),
        max_stale_days=3,
    ),
    StalenessSpec(
        domain="Rates Swaption Vol",
        pipeline_name="rates.vol",
        table="[rates].[fact_swaption_vol]",
        date_column="obs_date",
        key_column="surface_id",
        dim_table="[rates].[dim_vol_surface]",
        dim_join_col="id",
        dim_label_cols=("ccy", "data_type"),
        max_stale_days=3,
    ),
    StalenessSpec(
        domain="Rates Swaption Skew",
        pipeline_name="rates.skew_barclays_daily",
        table="[rates].[fact_swaption_skew]",
        date_column="obs_date",
        key_column="surface_id",
        dim_table="[rates].[dim_skew_surface]",
        dim_join_col="id",
        dim_label_cols=("ccy", "option_expiry"),
        max_stale_days=3,
    ),
    # ── FX ─────────────────────────────────────────────────────────
    StalenessSpec(
        domain="FX Vol",
        pipeline_name="fx.vol",
        table="[FX].[fact_vol]",
        date_column="obs_date",
        key_column="pair_id",
        dim_table="[FX].[dim_currency_pair]",
        dim_join_col="id",
        dim_label_cols=("base_ccy", "quote_ccy"),
        max_stale_days=3,
    ),
    # ── Commodities ────────────────────────────────────────────────
    StalenessSpec(
        domain="Commodities Spot",
        pipeline_name="commodities.spot",
        table="[commodities].[fact_spot]",
        date_column="obs_date",
        key_column="commodity_id",
        dim_table="[commodities].[dim_commodity]",
        dim_join_col="id",
        dim_label_cols=("symbol", "display_name"),
        max_stale_days=3,
    ),
    StalenessSpec(
        domain="Commodities Implied Vol",
        pipeline_name="commodities.vol",
        table="[commodities].[fact_implied_vol]",
        date_column="obs_date",
        key_column="commodity_id",
        dim_table="[commodities].[dim_commodity]",
        dim_join_col="id",
        dim_label_cols=("symbol", "display_name"),
        max_stale_days=3,
    ),
    StalenessSpec(
        domain="Commodities EIA",
        pipeline_name="commodities.eia",
        table="[commodities].[fact_eia]",
        date_column="obs_date",
        key_column="eia_series_id",
        dim_table="[commodities].[dim_eia_series]",
        dim_join_col="id",
        dim_label_cols=("series_name", "region"),
        max_stale_days=10,
    ),
    # ── Equities ───────────────────────────────────────────────────
    StalenessSpec(
        domain="Equity Indices",
        pipeline_name="equity.index",
        table="[equities].[fact_index_level]",
        date_column="obs_date",
        key_column="index_id",
        dim_table="[equities].[dim_index]",
        dim_join_col="id",
        dim_label_cols=("ticker", "display_name"),
        max_stale_days=3,
    ),
    StalenessSpec(
        domain="Equity VIX",
        pipeline_name="equity.vix",
        table="[equities].[fact_vix]",
        date_column="obs_date",
        key_column="ticker",
        dim_table=None,
        dim_label_cols=(),
        max_stale_days=3,
    ),
]


class StalenessMonitor:
    """Runs per-key freshness checks across all registered domain tables.

    For each StalenessSpec, queries ``MAX(date_column)`` grouped by
    ``key_column``, optionally joining to a dimension table for labels.
    Keys whose latest observation is older than ``max_stale_days`` are
    flagged.
    """

    def __init__(
        self,
        reader: AnalyticalReader,
        specs: list[StalenessSpec] | None = None,
        reference_date: date | None = None,
    ) -> None:
        self._reader = reader
        self._specs = specs or DEFAULT_SPECS
        self._reference_date = reference_date or date.today()

    @classmethod
    def from_config(
        cls,
        connector: MSSQLConnector,
        specs: list[StalenessSpec] | None = None,
        reference_date: date | None = None,
    ) -> StalenessMonitor:
        """Factory that builds an AnalyticalReader from a connector."""
        reader = AnalyticalReader(connector)
        return cls(reader, specs, reference_date)

    def run(self) -> StalenessReport:
        """Execute staleness checks across all specs and return a report."""
        now = datetime.now(timezone.utc)
        summaries: list[DomainSummary] = []

        for spec in self._specs:
            try:
                summary = self._check_spec(spec)
                summaries.append(summary)
                if summary.is_stale:
                    log.warning(
                        "staleness_detected",
                        domain=spec.domain,
                        stale_keys=summary.stale_keys,
                        total_keys=summary.total_keys,
                    )
                else:
                    log.info(
                        "staleness_ok",
                        domain=spec.domain,
                        total_keys=summary.total_keys,
                    )
            except Exception as exc:
                log.warning(
                    "staleness_check_failed",
                    domain=spec.domain,
                    error=str(exc)[:200],
                )
                summaries.append(
                    DomainSummary(
                        domain=spec.domain,
                        pipeline_name=spec.pipeline_name,
                        total_keys=0,
                        stale_keys=0,
                        fresh_keys=0,
                        latest_date=None,
                    )
                )

        return StalenessReport(
            checked_at=now,
            reference_date=self._reference_date,
            summaries=summaries,
        )

    def _check_spec(self, spec: StalenessSpec) -> DomainSummary:
        """Run staleness check for a single domain spec."""
        cutoff = self._reference_date - timedelta(days=spec.max_stale_days)

        if spec.dim_table and spec.dim_label_cols:
            df = self._query_with_dim(spec)
        else:
            df = self._query_no_dim(spec)

        if df.empty:
            return DomainSummary(
                domain=spec.domain,
                pipeline_name=spec.pipeline_name,
                total_keys=0,
                stale_keys=0,
                fresh_keys=0,
                latest_date=None,
            )

        # Legacy ODBC driver may return DATE as string — coerce to date
        df["latest_date"] = pd.to_datetime(df["latest_date"]).dt.date

        total_keys = len(df)
        stale_mask = df["latest_date"] < cutoff
        stale_df = df[stale_mask]
        stale_keys_count = len(stale_df)
        fresh_keys = total_keys - stale_keys_count

        latest_date = pd.Timestamp(df["latest_date"].max()).date()

        stale_items: list[StaleKey] = []
        for _, row in stale_df.iterrows():
            latest = pd.Timestamp(row["latest_date"]).date()
            days_behind = (self._reference_date - latest).days
            label = row.get("label", str(row["key_id"]))
            stale_items.append(
                StaleKey(
                    domain=spec.domain,
                    pipeline_name=spec.pipeline_name,
                    key_id=row["key_id"],
                    label=str(label),
                    latest_date=latest,
                    days_behind=days_behind,
                    max_stale_days=spec.max_stale_days,
                )
            )
        stale_items.sort(key=lambda k: k.days_behind, reverse=True)

        return DomainSummary(
            domain=spec.domain,
            pipeline_name=spec.pipeline_name,
            total_keys=total_keys,
            stale_keys=stale_keys_count,
            fresh_keys=fresh_keys,
            latest_date=latest_date,
            stale_items=stale_items,
        )

    def _query_with_dim(self, spec: StalenessSpec) -> pd.DataFrame:
        """Query MAX(date) per key, joining to dim table for labels."""
        label_select = ", ".join(f"d.[{c}]" for c in spec.dim_label_cols)
        label_concat = " + ' / ' + ".join(
            f"CAST(d.[{c}] AS VARCHAR(100))" for c in spec.dim_label_cols
        )
        sql = f"""
            SELECT
                f.[{spec.key_column}] AS key_id,
                {label_concat} AS label,
                {label_select},
                CAST(MAX(f.[{spec.date_column}]) AS DATE) AS latest_date
            FROM {spec.table} f
            JOIN {spec.dim_table} d ON d.[{spec.dim_join_col}] = f.[{spec.key_column}]
            GROUP BY f.[{spec.key_column}], {label_select}
            ORDER BY latest_date ASC
        """
        return self._reader.read_sql(sql)

    def _query_no_dim(self, spec: StalenessSpec) -> pd.DataFrame:
        """Query MAX(date) per key without a dimension join."""
        sql = f"""
            SELECT
                f.[{spec.key_column}] AS key_id,
                f.[{spec.key_column}] AS label,
                CAST(MAX(f.[{spec.date_column}]) AS DATE) AS latest_date
            FROM {spec.table} f
            GROUP BY f.[{spec.key_column}]
            ORDER BY latest_date ASC
        """
        return self._reader.read_sql(sql)
