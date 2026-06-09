"""Staleness alert email formatter.

Produces a cross-domain HTML email summarising which data series
in IMDR are stale (latest observation older than the configured
threshold). Designed to run once after the daily pipeline batch
completes, giving ops a single consolidated view.

When a domain has secondary breakdown dimensions configured (vendor,
frequency, …), the email renders one rollup table per dimension and
adds matching columns to the per-key detail table — so a partial
outage shows up as e.g. "vendor: bloomberg=5 stale" or
"frequency: HOURLY=3 stale" rather than a single averaged number.

Uses the same Jinja2 + inline-CSS pattern as the ingest formatters.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader

from imdr.healthchecks.staleness import (
    BreakdownRollup,
    DomainSummary,
    StaleKey,
    StalenessReport,
)

_SGT = timezone(timedelta(hours=8))
_TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"

# Stable display order for breakdowns in the email (alphabetical falls
# back to insertion order if a new dim isn't listed here).
_BREAKDOWN_ORDER = ("vendor", "frequency")


def _to_sgt(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(_SGT)


def _ordered_breakdown_names(by_breakdown: dict[str, Any]) -> list[str]:
    """Stable display order: known dims first, then any extras alphabetically."""
    known = [n for n in _BREAKDOWN_ORDER if n in by_breakdown]
    extras = sorted(n for n in by_breakdown if n not in _BREAKDOWN_ORDER)
    return known + extras


def _rollup_ctx(r: BreakdownRollup) -> dict[str, Any]:
    return {
        "code": r.code,
        "display_name": r.display_name,
        "total_keys": r.total_keys,
        "stale_keys": r.stale_keys,
        "fresh_keys": r.fresh_keys,
        "latest_date": str(r.latest_date) if r.latest_date else "N/A",
        "is_stale": r.is_stale,
    }


def _stale_item_ctx(sk: StaleKey, dim_names: list[str]) -> dict[str, Any]:
    return {
        "label": sk.label,
        "latest_date": str(sk.latest_date),
        "days_behind": sk.days_behind,
        "max_stale_days": sk.max_stale_days,
        "breakdown_codes": [sk.breakdown_code(n) or "-" for n in dim_names],
    }


def _domain_ctx(s: DomainSummary, *, include_items: bool) -> dict[str, Any]:
    dim_names = _ordered_breakdown_names(s.by_breakdown)
    ctx: dict[str, Any] = {
        "domain": s.domain,
        "pipeline_name": s.pipeline_name,
        "total_keys": s.total_keys,
        "stale_keys": s.stale_keys,
        "fresh_keys": s.fresh_keys,
        "latest_date": str(s.latest_date) if s.latest_date else "N/A",
        "has_breakdowns": s.has_breakdowns,
        "breakdown_dim_names": dim_names,
        "breakdowns": [
            {
                "name": dim,
                "rollups": [_rollup_ctx(r) for r in s.rollup(dim)],
            }
            for dim in dim_names
        ],
    }
    if include_items:
        ctx["stale_items"] = [_stale_item_ctx(sk, dim_names) for sk in s.stale_items]
    return ctx


def _global_breakdown_totals(report: StalenessReport) -> list[dict[str, Any]]:
    """Subject-line / summary input: stale counts per dim, per code, across all domains."""
    seen: list[str] = []
    for s in report.summaries:
        for dim in s.by_breakdown:
            if dim not in seen:
                seen.append(dim)
    ordered = [n for n in _BREAKDOWN_ORDER if n in seen] + [n for n in seen if n not in _BREAKDOWN_ORDER]
    out: list[dict[str, Any]] = []
    for dim in ordered:
        totals = report.breakdown_totals(dim)
        if totals:
            out.append(
                {
                    "name": dim,
                    "totals": [
                        {"code": code, "stale_keys": n}
                        for code, n in sorted(totals.items())
                    ],
                }
            )
    return out


class StalenessAlertFormatter:
    """Formats the cross-domain staleness alert email."""

    def __init__(self) -> None:
        self._env = Environment(
            loader=FileSystemLoader(str(_TEMPLATE_DIR)),
            autoescape=True,
        )
        self._template = self._env.get_template("staleness_alert.html")

    def format_subject(
        self,
        report: StalenessReport | None = None,
        **kwargs: Any,
    ) -> str:
        if report and report.has_stale:
            n_keys = report.total_stale_keys
            n_domains = len(report.stale_domains)
            tags: list[str] = []
            for dim in (n for n in _BREAKDOWN_ORDER):
                totals = report.breakdown_totals(dim)
                if totals:
                    pieces = ",".join(f"{c}={v}" for c, v in sorted(totals.items()))
                    tags.append(f"{dim}: {pieces}")
            extra = f" | {' | '.join(tags)}" if tags else ""
            return (
                f"[IMDR] STALENESS ALERT | "
                f"{n_keys} stale key(s) across {n_domains} domain(s)"
                f"{extra} | {report.reference_date}"
            )
        ref = report.reference_date if report else "N/A"
        return f"[IMDR] Staleness Check OK | All domains fresh | {ref}"

    def format_body(
        self,
        report: StalenessReport | None = None,
        **kwargs: Any,
    ) -> str:
        if report is None:
            return "<p>No staleness report available.</p>"

        now_utc = datetime.now(timezone.utc)
        run_time_utc = now_utc.strftime("%Y-%m-%d %H:%M:%S UTC")
        run_time_sgt = _to_sgt(now_utc).strftime("%H:%M:%S SGT")

        ctx = {
            "has_stale": report.has_stale,
            "reference_date": str(report.reference_date),
            "checked_at": report.checked_at.strftime("%Y-%m-%d %H:%M:%S UTC"),
            "run_time_utc": run_time_utc,
            "run_time_sgt": run_time_sgt,
            "total_stale_keys": report.total_stale_keys,
            "n_stale_domains": len(report.stale_domains),
            "n_healthy_domains": len(report.healthy_domains),
            "n_total_domains": len(report.summaries),
            "global_breakdowns": _global_breakdown_totals(report),
            "stale_domains": [
                _domain_ctx(s, include_items=True) for s in report.stale_domains
            ],
            "healthy_domains": [
                _domain_ctx(s, include_items=False) for s in report.healthy_domains
            ],
        }
        return self._template.render(**ctx)
