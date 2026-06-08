"""Per-country econ-ingest DB snapshot for notification emails.

Reads from econ.dim_indicator + econ.fact_indicator after a fetcher run to
produce the row-level data the formatter needs:
  - what landed THIS run (rows where ingested_at >= run_started_at)
  - per-indicator coverage (n_obs, first/last obs, last value, last ingest)
  - staleness flag computed from frequency cadence

Read-only. Domain-agnostic but currently scoped by ``country_code`` because
each country gets its own orchestrator/email."""

from __future__ import annotations

import datetime
from dataclasses import dataclass

from sqlalchemy import text

from imdr.config.settings import Settings
from imdr.connectors.mssql import MSSQLConnector


# Staleness threshold = 2 x typical cadence, in days. Series whose newest obs_date
# is older than this are flagged as stale in the email.
_STALE_DAYS: dict[str, int] = {
    "DAILY": 5,
    "WEEKLY": 14,
    "MONTHLY": 60,
    "QUARTERLY": 180,
    "SEMIANNUAL": 240,
    "ANNUAL": 730,
}


@dataclass(frozen=True)
class IndicatorSnapshot:
    imdr_code: str
    display_name: str
    vendor_code: str
    frequency_code: str
    category_code: str
    n_obs: int
    first_obs: datetime.date | None
    last_obs: datetime.date | None
    last_value: float | None
    last_ingest: datetime.datetime | None
    new_obs_this_run: int
    is_stale: bool
    days_since_last_obs: int | None


def snapshot(
    settings: Settings,
    *,
    country_code: str,
    run_started_at: datetime.datetime,
    frequency_codes: list[str] | None = None,
) -> list[IndicatorSnapshot]:
    """Return one row per active indicator for ``country_code``.

    ``run_started_at`` is the UTC datetime captured immediately before the
    first fetcher subprocess was launched -- rows with ingested_at at or
    after this timestamp are attributed to THIS run.

    ``frequency_codes`` narrows the result (e.g. ``["WEEKLY"]`` for the
    weekly orchestrator); ``None`` returns all frequencies.
    """
    today = datetime.date.today()
    freq_filter = ""
    params: dict[str, object] = {"cc": country_code, "t0": run_started_at}
    if frequency_codes:
        placeholders = ", ".join(f":freq_{i}" for i in range(len(frequency_codes)))
        freq_filter = f" AND f.frequency_code IN ({placeholders})"
        for i, code in enumerate(frequency_codes):
            params[f"freq_{i}"] = code

    sql = f"""
        WITH agg AS (
            SELECT
                indicator_id,
                COUNT(*)                                              AS n_obs,
                MIN(obs_date)                                         AS first_obs,
                MAX(obs_date)                                         AS last_obs,
                MAX(ingested_at)                                      AS last_ingest,
                SUM(CASE WHEN ingested_at >= :t0 THEN 1 ELSE 0 END)   AS new_obs
            FROM econ.fact_indicator
            GROUP BY indicator_id
        ),
        ranked AS (
            SELECT
                indicator_id,
                obs_date,
                value,
                ROW_NUMBER() OVER (
                    PARTITION BY indicator_id
                    ORDER BY obs_date DESC, vintage DESC
                ) AS rn
            FROM econ.fact_indicator
        )
        SELECT
            d.imdr_code,
            d.display_name,
            v.vendor_code,
            f.frequency_code,
            dc.category_code,
            COALESCE(a.n_obs, 0)   AS n_obs,
            a.first_obs,
            a.last_obs,
            a.last_ingest,
            COALESCE(a.new_obs, 0) AS new_obs,
            r.value                AS last_value
        FROM econ.dim_indicator d
        JOIN dbo.dim_country             c  ON c.id  = d.country_id
        JOIN dbo.dim_vendor              v  ON v.id  = d.vendor_id
        JOIN dbo.dim_frequency           f  ON f.id  = d.frequency_id
        JOIN econ.dim_indicator_category dc ON dc.id = d.category_id
        LEFT JOIN agg    a ON a.indicator_id = d.id
        LEFT JOIN ranked r ON r.indicator_id = d.id AND r.rn = 1
        WHERE c.country_code = :cc
          AND d.is_active    = 1
          {freq_filter}
        ORDER BY dc.category_code, d.imdr_code
    """

    connector = MSSQLConnector(settings)
    try:
        with connector.session() as session:
            rows = session.execute(text(sql), params).all()
    finally:
        connector.dispose()

    out: list[IndicatorSnapshot] = []
    for row in rows:
        first_obs = _as_date(row.first_obs)
        last_obs = _as_date(row.last_obs)
        days_since = (today - last_obs).days if last_obs else None
        threshold = _STALE_DAYS.get(row.frequency_code)
        is_stale = (
            threshold is not None
            and days_since is not None
            and days_since > threshold
        )
        out.append(IndicatorSnapshot(
            imdr_code=row.imdr_code,
            display_name=row.display_name,
            vendor_code=row.vendor_code,
            frequency_code=row.frequency_code,
            category_code=row.category_code,
            n_obs=int(row.n_obs),
            first_obs=first_obs,
            last_obs=last_obs,
            last_value=(float(row.last_value) if row.last_value is not None else None),
            last_ingest=row.last_ingest,
            new_obs_this_run=int(row.new_obs),
            is_stale=is_stale,
            days_since_last_obs=days_since,
        ))
    return out


def _as_date(v: object) -> datetime.date | None:
    """Legacy 'SQL Server' ODBC driver returns DATE columns as strings."""
    if v is None:
        return None
    if isinstance(v, datetime.date):
        return v
    if isinstance(v, str):
        return datetime.date.fromisoformat(v[:10])
    return None
