"""Country econ-ingest email formatter.

Produced by ``scripts.econ._country_runner`` after each per-country
orchestrator (KR / ID / …) finishes running its fetcher subprocesses.
The body groups indicators by ``econ.dim_indicator_category`` and folds
in DB-derived freshness + staleness flags.

Parametrised by ``country_label`` (2-letter ISO code in the subject),
``country_name`` (display string in the body), and ``orchestrator_path``
(dotted module path for the orchestrator that produced the run).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

from jinja2 import Environment, FileSystemLoader

from imdr.notifications.econ_snapshot import IndicatorSnapshot


_SGT = timezone(timedelta(hours=8))
_TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"

_BANNER_COLOR = {
    "OK": "#27ae60",
    "PARTIAL": "#f39c12",
    "FAIL": "#e74c3c",
}


def _to_sgt(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(_SGT)


def _status(failed_pipelines: list[str], stale_count: int) -> str:
    if failed_pipelines:
        return "FAIL" if len(failed_pipelines) > 1 else "PARTIAL"
    if stale_count:
        return "PARTIAL"
    return "OK"


def _fmt_value(v: float | None) -> str:
    if v is None:
        return "&mdash;"
    av = abs(v)
    if av >= 1_000_000:
        return f"{v:,.0f}"
    if av >= 100:
        return f"{v:,.2f}"
    return f"{v:,.4f}"


def _build_categories(rows: Iterable[IndicatorSnapshot]) -> list[dict[str, Any]]:
    """Group per-indicator snapshots by category for the template."""
    bucket: dict[str, list[IndicatorSnapshot]] = {}
    for r in rows:
        bucket.setdefault(r.category_code, []).append(r)

    cats: list[dict[str, Any]] = []
    for code in sorted(bucket):
        items = bucket[code]
        cats.append({
            "code": code,
            "n_indicators": len(items),
            "n_new_rows": sum(r.new_obs_this_run for r in items),
            "n_with_new": sum(1 for r in items if r.new_obs_this_run > 0),
            "n_stale": sum(1 for r in items if r.is_stale),
            "rows": [
                {
                    "imdr_code": r.imdr_code,
                    "display_name": r.display_name,
                    "vendor": r.vendor_code,
                    "frequency": r.frequency_code,
                    "n_obs": r.n_obs,
                    "first_obs": r.first_obs.isoformat() if r.first_obs else "",
                    "last_obs": r.last_obs.isoformat() if r.last_obs else "",
                    "last_value": _fmt_value(r.last_value),
                    "days_since": r.days_since_last_obs,
                    "new_obs": r.new_obs_this_run,
                    "is_stale": r.is_stale,
                }
                for r in sorted(items, key=lambda x: x.imdr_code)
            ],
        })
    return cats


class CountryEconIngestFormatter:
    """HTML email formatter for per-country econ orchestrator runs."""

    def __init__(
        self,
        *,
        country_label: str,
        country_name: str,
        orchestrator_path: str,
    ) -> None:
        self._country_label = country_label
        self._country_name = country_name
        self._orchestrator_path = orchestrator_path
        self._env = Environment(
            loader=FileSystemLoader(str(_TEMPLATE_DIR)),
            autoescape=True,
        )
        self._template = self._env.get_template("country_econ_ingest.html")

    def format_subject(
        self,
        *,
        run_name: str,
        new_rows: int,
        indicators_updated: int,
        stale_count: int,
        failed_pipelines: list[str],
        **_: Any,
    ) -> str:
        status = _status(failed_pipelines, stale_count)
        return (
            f"[IMDR] {self._country_label} Econ {run_name} {status} "
            f"| {new_rows} new obs / {indicators_updated} indicators updated"
            f"{f' | {stale_count} stale' if stale_count else ''}"
            f"{f' | {len(failed_pipelines)} failed' if failed_pipelines else ''}"
        )

    def format_body(
        self,
        *,
        run_name: str,
        run_started_at: datetime,
        run_completed_at: datetime,
        duration_s: float,
        pipelines: list[dict[str, Any]],
        failed_pipelines: list[str],
        snapshots: list[IndicatorSnapshot],
        frequency_scope: list[str],
        **_: Any,
    ) -> str:
        new_rows = sum(s.new_obs_this_run for s in snapshots)
        indicators_updated = sum(1 for s in snapshots if s.new_obs_this_run > 0)
        stale = [s for s in snapshots if s.is_stale]
        categories = _build_categories(snapshots)
        status = _status(failed_pipelines, len(stale))

        return self._template.render(
            country_label=self._country_label,
            country_name=self._country_name,
            orchestrator_path=self._orchestrator_path,
            run_name=run_name,
            status=status,
            banner_color=_BANNER_COLOR.get(status, "#1a237e"),
            run_started_utc=run_started_at.strftime("%Y-%m-%d %H:%M:%S UTC"),
            run_started_sgt=_to_sgt(run_started_at).strftime("%Y-%m-%d %H:%M:%S SGT"),
            run_completed_utc=run_completed_at.strftime("%Y-%m-%d %H:%M:%S UTC"),
            duration_s=f"{duration_s:.1f}",
            frequency_scope=", ".join(frequency_scope) if frequency_scope else "ALL",
            pipelines=pipelines,
            failed_pipelines=failed_pipelines,
            n_pipelines=len(pipelines),
            n_failed=len(failed_pipelines),
            new_rows=new_rows,
            indicators_total=len(snapshots),
            indicators_updated=indicators_updated,
            categories=categories,
            stale_rows=[
                {
                    "imdr_code": s.imdr_code,
                    "frequency": s.frequency_code,
                    "category": s.category_code,
                    "last_obs": s.last_obs.isoformat() if s.last_obs else "",
                    "days_since": s.days_since_last_obs,
                }
                for s in sorted(stale, key=lambda x: (x.days_since_last_obs or 0), reverse=True)
            ],
            n_stale=len(stale),
        )
