"""Cross-domain data staleness monitor.

Queries every fact table in IMDR at the *per-key* level (per-curve,
per-pair, per-commodity, per-index) and flags any key whose latest
observation is older than its configured threshold. Optional secondary
breakdowns (vendor, frequency, …) let the monitor surface partial
outages — e.g. "Bloomberg dropped DAILY but Citi kept HOURLY" — that
would otherwise be averaged away by a single-column GROUP BY.

This module is domain-agnostic — each domain registers a StalenessSpec
that describes how to query its table and which secondary dimensions
its schema supports. The monitor runs all specs and returns a unified
StalenessReport.

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


# ── Breakdown dimensions ──────────────────────────────────────────────


@dataclass(frozen=True)
class BreakdownDim:
    """A secondary grouping dimension for staleness analysis.

    Specs opt in to breakdowns by listing them in ``StalenessSpec.breakdowns``.
    The monitor adds the dim's FK column to the GROUP BY, joins the dim
    table for human-readable code/name, and emits a separate rollup per
    breakdown in the resulting DomainSummary.

    The output column aliases are derived from ``name``: a breakdown
    named ``"vendor"`` produces ``vendor_code`` and ``vendor_name``
    columns in the result DataFrame (and on each StaleKey).

    Attributes:
        name:        Short identifier used as dict key and column-alias
                     prefix (e.g. "vendor", "frequency").
        fk_column:   FK column on the fact table (e.g. "vendor_id").
        dim_table:   Fully-qualified dim table (e.g. "[dbo].[dim_vendor]").
        code_column: Short-code column on the dim (e.g. "vendor_code").
        name_column: Display-name column on the dim (e.g. "display_name").
        join_col:    PK column on the dim table.
    """

    name: str
    fk_column: str
    dim_table: str
    code_column: str
    name_column: str
    join_col: str = "id"

    @property
    def code_alias(self) -> str:
        return f"{self.name}_code"

    @property
    def name_alias(self) -> str:
        return f"{self.name}_name"


# Predefined breakdowns. Specs reference these constants rather than
# repeating column names — keeps the spec list readable and lets a
# rename in dim_vendor / dim_frequency stay in one place.

VENDOR_BREAKDOWN = BreakdownDim(
    name="vendor",
    fk_column="vendor_id",
    dim_table="[dbo].[dim_vendor]",
    code_column="vendor_code",
    name_column="display_name",
)

FREQUENCY_BREAKDOWN = BreakdownDim(
    name="frequency",
    fk_column="frequency_id",
    dim_table="[dbo].[dim_frequency]",
    code_column="frequency_code",
    name_column="display_name",
)


# ── Spec ──────────────────────────────────────────────────────────────


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
        dim_filter:     Optional SQL fragment applied as WHERE on the dim
                        table (e.g. "curve_status <> 'ceased'") to skip
                        decommissioned series. Only applied when dim_table
                        is set.
        breakdowns:     Optional secondary group-by dimensions (vendor,
                        frequency, …). When non-empty, the query groups by
                        ``(key, *breakdown_fks)`` and the resulting
                        DomainSummary carries one rollup per breakdown.
        max_stale_days: How many days behind the reference date before a
                        key is flagged stale. Counted in *business days*
                        when ``business_days`` is set, else calendar days.
        business_days:  When True, the age of a key is measured in
                        business days (Mon–Fri), so a Friday observation
                        checked on Monday reads as 1 day behind, not 3.
                        Use for daily market-data feeds that only publish
                        on weekdays; leave False for calendar-cadence
                        feeds (weekly EIA, monthly econ) where a fixed
                        calendar window is the right gauge.
    """

    domain: str
    pipeline_name: str
    table: str
    date_column: str
    key_column: str
    dim_table: str | None = None
    dim_join_col: str = "id"
    dim_label_cols: tuple[str, ...] = ()
    dim_filter: str | None = None
    breakdowns: tuple[BreakdownDim, ...] = ()
    max_stale_days: int = 3
    business_days: bool = False

    @property
    def has_dim(self) -> bool:
        return bool(self.dim_table and self.dim_label_cols)

    @property
    def has_breakdowns(self) -> bool:
        return bool(self.breakdowns)


# ── Result types ──────────────────────────────────────────────────────


@dataclass
class StaleKey:
    """One stale row from the per-key staleness query.

    ``breakdowns`` maps each enabled breakdown's name to its (code, name)
    label tuple — e.g. ``{"vendor": ("bloomberg", "Bloomberg"),
    "frequency": ("DAILY", "Daily")}``. Empty when the spec has no
    breakdowns configured.
    """

    domain: str
    pipeline_name: str
    key_id: Any
    label: str
    latest_date: date
    days_behind: int
    max_stale_days: int
    breakdowns: dict[str, tuple[str, str]] = field(default_factory=dict)

    def breakdown_code(self, name: str) -> str | None:
        pair = self.breakdowns.get(name)
        return pair[0] if pair else None

    def breakdown_name(self, name: str) -> str | None:
        pair = self.breakdowns.get(name)
        return pair[1] if pair else None


@dataclass
class BreakdownRollup:
    """Per-value freshness rollup for a single breakdown dimension.

    e.g. for the ``vendor`` breakdown: one rollup per vendor_code,
    counting how many of that vendor's keys are stale vs fresh.
    """

    dim_name: str
    code: str
    display_name: str
    total_keys: int
    stale_keys: int
    fresh_keys: int
    latest_date: date | None

    @property
    def is_stale(self) -> bool:
        return self.stale_keys > 0


@dataclass
class DomainSummary:
    """Staleness summary for one domain.

    ``total_keys`` counts grouping units, which is one row per key when
    no breakdowns apply and one row per (key, *breakdowns) tuple when
    they do. This keeps the arithmetic consistent: a curve served by
    two vendors at two frequencies counts four times if both dims are
    tracked, since each (vendor, frequency) feed is a separate
    monitoring target.

    ``by_breakdown`` is keyed by the breakdown's ``name`` and holds the
    per-value rollup — e.g. ``by_breakdown["vendor"]`` lists one entry
    per distinct vendor seen, with stale/fresh counts.
    """

    domain: str
    pipeline_name: str
    total_keys: int
    stale_keys: int
    fresh_keys: int
    latest_date: date | None
    stale_items: list[StaleKey] = field(default_factory=list)
    by_breakdown: dict[str, list[BreakdownRollup]] = field(default_factory=dict)

    @property
    def is_stale(self) -> bool:
        return self.stale_keys > 0

    @property
    def has_breakdowns(self) -> bool:
        return bool(self.by_breakdown)

    def rollup(self, dim_name: str) -> list[BreakdownRollup]:
        """Convenience accessor — empty list if dim not tracked."""
        return self.by_breakdown.get(dim_name, [])


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

    def breakdown_totals(self, dim_name: str) -> dict[str, int]:
        """Aggregate stale key counts for one breakdown across all domains.

        e.g. ``report.breakdown_totals("vendor")`` returns
        ``{"bloomberg": 12, "citi_velocity": 0}``. Domains without that
        breakdown are skipped. Returned dict is keyed by ``code`` so it's
        stable for subject-line use.
        """
        totals: dict[str, int] = {}
        for s in self.summaries:
            for r in s.rollup(dim_name):
                if r.stale_keys:
                    totals[r.code] = totals.get(r.code, 0) + r.stale_keys
        return totals


# ── Default specs for all IMDR domains ────────────────────────────────

# These match the current schema. When new domains are added, add a
# spec here. Tables that already carry vendor_id / frequency_id (per
# migrations 017, 020, 023, 024, 029) opt in via ``breakdowns``.

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
        dim_filter="curve_status <> 'ceased'",
        breakdowns=(VENDOR_BREAKDOWN, FREQUENCY_BREAKDOWN),
        # Daily weekday-only feed (Citi EOD). Business-day mode so a
        # Friday obs read on Monday isn't 3 "stale" calendar days, and a
        # 2-day threshold flags a genuine per-curve stall (e.g. AUD 3s6s
        # lagging its siblings) without firing on same-day publish lag.
        max_stale_days=2,
        business_days=True,
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
        breakdowns=(VENDOR_BREAKDOWN,),
        max_stale_days=3,
    ),
    StalenessSpec(
        domain="Rates Benchmark",
        pipeline_name="rates.bench_rates",
        table="[rates].[fact_bench_rates]",
        date_column="obs_date",
        key_column="cb_id",
        dim_table="[rates].[dim_central_bank]",
        dim_join_col="id",
        dim_label_cols=("currency", "cb_code"),
        breakdowns=(VENDOR_BREAKDOWN,),
        max_stale_days=3,
    ),
    # ── FX ─────────────────────────────────────────────────────────
    StalenessSpec(
        domain="FX Rate",
        pipeline_name="fx.citi_rate",
        table="[fx].[fact_fx_rate]",
        date_column="obs_ts",
        key_column="pair_id",
        dim_table="[fx].[dim_currency_pair]",
        dim_join_col="id",
        dim_label_cols=("base_ccy", "quote_ccy"),
        breakdowns=(VENDOR_BREAKDOWN, FREQUENCY_BREAKDOWN),
        max_stale_days=3,
    ),
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


# ── Age arithmetic ────────────────────────────────────────────────────


def _days_behind(latest: date, reference: date, business_days: bool = False) -> int:
    """Age of an observation relative to the reference date.

    Calendar mode is a plain day subtraction. Business-day mode counts
    only Mon–Fri, so a Friday observation checked on the following Monday
    is 1 business day behind (not 3) — the right gauge for daily market
    feeds that never publish over a weekend. Holidays are not modelled;
    weekend-awareness removes the dominant source of false staleness and
    a genuine multi-day stall still clears the threshold within a day or
    two of trading.
    """
    if latest >= reference:
        return 0
    if not business_days:
        return (reference - latest).days
    days = 0
    d = latest
    while d < reference:
        d += timedelta(days=1)
        if d.weekday() < 5:  # Mon–Fri
            days += 1
    return days


# ── SQL builder ───────────────────────────────────────────────────────


def _build_query(spec: StalenessSpec) -> str:
    """Compose a per-key staleness SQL query from a spec.

    The query emits one row per grouping unit:
      - ``(key)`` when no breakdowns are configured
      - ``(key, *breakdown_fks)`` when breakdowns are configured

    Identifiers are taken from the spec verbatim and wrapped in brackets
    by the caller; specs are static module-level data, so this is safe
    against injection by construction.
    """
    select: list[str] = [f"f.[{spec.key_column}] AS key_id"]
    group: list[str] = [f"f.[{spec.key_column}]"]
    joins: list[str] = []
    where: list[str] = []

    # Dimension join for human-readable label
    if spec.has_dim:
        label_expr = " + ' / ' + ".join(
            f"CAST(d.[{c}] AS VARCHAR(100))" for c in spec.dim_label_cols
        )
        select.append(f"{label_expr} AS label")
        for col in spec.dim_label_cols:
            select.append(f"d.[{col}]")
            group.append(f"d.[{col}]")
        joins.append(
            f"JOIN {spec.dim_table} d ON d.[{spec.dim_join_col}] = f.[{spec.key_column}]"
        )
        if spec.dim_filter:
            where.append(f"d.{spec.dim_filter}")
    else:
        select.append(f"CAST(f.[{spec.key_column}] AS VARCHAR(100)) AS label")

    # Secondary breakdowns (vendor, frequency, …)
    for i, b in enumerate(spec.breakdowns):
        alias = f"b{i}"
        select.append(f"{alias}.[{b.code_column}] AS {b.code_alias}")
        select.append(f"{alias}.[{b.name_column}] AS {b.name_alias}")
        group.append(f"{alias}.[{b.code_column}]")
        group.append(f"{alias}.[{b.name_column}]")
        joins.append(
            f"JOIN {b.dim_table} {alias} "
            f"ON {alias}.[{b.join_col}] = f.[{b.fk_column}]"
        )

    select.append(f"CAST(MAX(f.[{spec.date_column}]) AS DATE) AS latest_date")

    parts = [
        f"SELECT {', '.join(select)}",
        f"FROM {spec.table} f",
        *joins,
    ]
    if where:
        parts.append("WHERE " + " AND ".join(where))
    parts.append("GROUP BY " + ", ".join(group))
    parts.append("ORDER BY latest_date ASC")
    return "\n".join(parts)


# ── Monitor ───────────────────────────────────────────────────────────


class StalenessMonitor:
    """Runs per-key freshness checks across all registered domain tables.

    For each StalenessSpec, queries ``MAX(date_column)`` grouped by
    ``key_column`` (and any configured breakdown FKs), optionally
    joining to a dim table for labels. Keys whose latest observation is
    older than ``max_stale_days`` are flagged.
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
                        breakdowns={
                            dim: {r.code: r.stale_keys for r in rollups if r.stale_keys}
                            for dim, rollups in summary.by_breakdown.items()
                        } or None,
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
        """Run staleness check for a single domain spec.

        A key is stale when its age (calendar or business days, per the
        spec) exceeds ``max_stale_days``. Expressing the test as
        ``days_behind > max_stale_days`` is exactly equivalent to the
        old ``latest_date < reference - max_stale_days`` cutoff in
        calendar mode, and generalises cleanly to business-day mode.
        """
        df = self._reader.read_sql(_build_query(spec))

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
        df["days_behind"] = df["latest_date"].map(
            lambda d: _days_behind(d, self._reference_date, spec.business_days)
        )

        total_keys = len(df)
        stale_mask = df["days_behind"] > spec.max_stale_days
        stale_df = df[stale_mask]
        stale_keys_count = len(stale_df)
        latest_date = pd.Timestamp(df["latest_date"].max()).date()

        return DomainSummary(
            domain=spec.domain,
            pipeline_name=spec.pipeline_name,
            total_keys=total_keys,
            stale_keys=stale_keys_count,
            fresh_keys=total_keys - stale_keys_count,
            latest_date=latest_date,
            stale_items=self._build_stale_items(stale_df, spec),
            by_breakdown=self._build_breakdowns(df, spec),
        )

    def _build_stale_items(
        self, stale_df: pd.DataFrame, spec: StalenessSpec
    ) -> list[StaleKey]:
        """Convert stale rows into StaleKey items, worst-first."""
        items: list[StaleKey] = []
        for _, row in stale_df.iterrows():
            latest = pd.Timestamp(row["latest_date"]).date()
            days_behind = (
                int(row["days_behind"])
                if "days_behind" in row.index
                else _days_behind(latest, self._reference_date, spec.business_days)
            )
            label = row.get("label", str(row["key_id"]))
            breakdowns = {
                b.name: (str(row[b.code_alias]), str(row[b.name_alias]))
                for b in spec.breakdowns
                if b.code_alias in row.index
            }
            items.append(
                StaleKey(
                    domain=spec.domain,
                    pipeline_name=spec.pipeline_name,
                    key_id=row["key_id"],
                    label=str(label),
                    latest_date=latest,
                    days_behind=days_behind,
                    max_stale_days=spec.max_stale_days,
                    breakdowns=breakdowns,
                )
            )
        items.sort(key=lambda k: k.days_behind, reverse=True)
        return items

    def _build_breakdowns(
        self, df: pd.DataFrame, spec: StalenessSpec
    ) -> dict[str, list[BreakdownRollup]]:
        """Aggregate per-breakdown stale/fresh counts for a domain.

        For each enabled breakdown, group the result DataFrame on that
        single column (collapsing any other dims) and produce a rollup
        per distinct value. This way two breakdowns produce two
        independent views of the same underlying rows.
        """
        out: dict[str, list[BreakdownRollup]] = {}
        if not spec.has_breakdowns:
            return out

        for b in spec.breakdowns:
            if b.code_alias not in df.columns:
                continue
            rollups: list[BreakdownRollup] = []
            for (code, name), group in df.groupby([b.code_alias, b.name_alias]):
                stale_n = int((group["days_behind"] > spec.max_stale_days).sum())
                rollups.append(
                    BreakdownRollup(
                        dim_name=b.name,
                        code=str(code),
                        display_name=str(name),
                        total_keys=len(group),
                        stale_keys=stale_n,
                        fresh_keys=len(group) - stale_n,
                        latest_date=pd.Timestamp(group["latest_date"].max()).date(),
                    )
                )
            rollups.sort(key=lambda r: r.code)
            out[b.name] = rollups
        return out
