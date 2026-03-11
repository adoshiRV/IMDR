"""Weekly health dashboard email formatter — Jinja2 + inline CSS for Outlook."""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pandas as pd
from jinja2 import Environment, FileSystemLoader
from markupsafe import Markup

from imdr.healthchecks.dashboard import DomainReport, WeeklyDashboard

_SGT = timezone(timedelta(hours=8))
_TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"


def _to_sgt(dt: datetime) -> datetime:
    """Convert a UTC datetime to SGT (UTC+8)."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(_SGT)


def _df_to_html_inline(df: pd.DataFrame, max_rows: int = 50) -> str:
    """Convert DataFrame to HTML table with inline CSS for Outlook."""
    if df is None or df.empty:
        return '<p style="color:#888;padding:4px 0;">No data.</p>'

    truncated = len(df) > max_rows
    display_df = df.head(max_rows) if truncated else df

    html = display_df.to_html(index=False, border=0, na_rep="—")

    # Inject inline styles
    html = re.sub(
        r"<table",
        '<table cellpadding="5" cellspacing="0" '
        'style="border-collapse:collapse;border:1px solid #ddd;font-size:12px;'
        'width:96%;margin:4px auto"',
        html,
    )
    html = re.sub(
        r"<th>",
        '<th style="border:1px solid #555;padding:6px;text-align:left;'
        'background:#1a1a2e;color:#fff;font-size:11px;">',
        html,
    )
    html = re.sub(
        r"<td>",
        '<td style="border:1px solid #ddd;padding:4px;font-size:12px;">',
        html,
    )
    # Alternate row shading
    rows = re.findall(r"<tr>(.*?)</tr>", html, re.DOTALL)
    for i, row_content in enumerate(rows):
        if i == 0:
            continue  # skip header
        bg = "#f5f5f5" if i % 2 == 1 else "#ffffff"
        old = f"<tr>{row_content}</tr>"
        new = f'<tr style="background:{bg}">{row_content}</tr>'
        html = html.replace(old, new, 1)

    if truncated:
        remaining = len(df) - max_rows
        html += (
            f'<p style="color:#888;font-size:11px;padding:4px 8px;">'
            f"... and {remaining} more rows</p>"
        )

    return html


def _domain_context(domain: DomainReport) -> dict[str, Any]:
    """Build template context for one domain."""
    # Health check details — rolling window (1 report) or per-year (N reports)
    year_health = []
    rolling_window = len(domain.health_reports) < len(domain.years)

    if rolling_window:
        # Dashboard mode: single health report for rolling 30-day window
        for report in domain.health_reports:
            checks = [
                {"name": r.check_name, "status": r.status.value, "message": r.message}
                for r in report.results
            ]
            year_health.append({"year": "Last 30 days", "passed": report.passed, "checks": checks})
    else:
        # Per-year mode (individual report scripts)
        for i, report in enumerate(domain.health_reports):
            year = domain.years[i] if i < len(domain.years) else "?"
            checks = [
                {"name": r.check_name, "status": r.status.value, "message": r.message}
                for r in report.results
            ]
            year_health.append({"year": year, "passed": report.passed, "checks": checks})

    # Quality results
    quality = []
    for qr in domain.quality_results:
        entry: dict[str, Any] = {
            "name": qr.check_name,
            "status": qr.status.value,
            "category": qr.category,
            "message": qr.message,
            "has_summary": qr.summary is not None and not qr.summary.empty,
            "summary_html": Markup(_df_to_html_inline(qr.summary, max_rows=30)),
            "flagged_count": len(qr.flagged) if qr.flagged is not None else 0,
            "flagged_html": Markup(_df_to_html_inline(
                qr.flagged.head(5) if qr.flagged is not None and not qr.flagged.empty else pd.DataFrame(),
                max_rows=5,
            )),
        }
        quality.append(entry)

    # Coverage tables
    coverage_tables = []
    for name, df in domain.coverage.tables.items():
        label = name.replace("_", " ").title()
        coverage_tables.append({
            "label": label,
            "html": Markup(_df_to_html_inline(df)),
        })

    # Cleaning summary
    cleaning_rules = []
    total_unique = 0
    all_ids: dict[str, set[int]] = {}
    for cr in domain.cleaning_results:
        ids = {a.row_id for a in cr.actions}
        all_ids[cr.rule_name] = ids
        cleaning_rules.append({
            "name": cr.rule_name,
            "count": cr.count,
        })

    # Compute unique (non-overlapping) per rule
    if all_ids:
        union_all = set()
        for ids in all_ids.values():
            union_all |= ids
        total_unique = len(union_all)

        for entry in cleaning_rules:
            rule_ids = all_ids[entry["name"]]
            other_ids = set()
            for rn, ids in all_ids.items():
                if rn != entry["name"]:
                    other_ids |= ids
            unique = len(rule_ids - other_ids)
            entry["unique"] = unique
            entry["overlap"] = entry["count"] - unique

    return {
        "domain_name": domain.domain_name,
        "table_name": domain.table_name,
        "health_passed": domain.health_passed,
        "year_health": year_health,
        "years_passed": sum(1 for r in domain.health_reports if r.passed),
        "years_total": len(domain.health_reports),
        "coverage_tables": coverage_tables,
        "coverage_summary": domain.coverage.summary,
        "quality": quality,
        "cleaning_rules": cleaning_rules,
        "total_cleaning_flags": total_unique,
    }


class WeeklyDashboardFormatter:
    """Formats the weekly health dashboard email."""

    def __init__(self) -> None:
        self._env = Environment(
            loader=FileSystemLoader(str(_TEMPLATE_DIR)),
            autoescape=True,
        )
        self._env.filters["df_html"] = _df_to_html_inline
        self._template = self._env.get_template("weekly_dashboard.html")

    def format_subject(self, dashboard: WeeklyDashboard) -> str:
        status = "ALL PASS" if dashboard.all_passed else "ISSUES FOUND"
        date_str = dashboard.generated_at.strftime("%Y-%m-%d")
        n_domains = len(dashboard.domains)
        return f"[IMDR] Weekly Health Dashboard {status} | {date_str} | {n_domains} domains"

    def format_body(self, dashboard: WeeklyDashboard) -> str:
        now_utc = dashboard.generated_at
        domains = [_domain_context(d) for d in dashboard.domains]

        ctx = {
            "all_passed": dashboard.all_passed,
            "date_str": now_utc.strftime("%Y-%m-%d"),
            "day_name": now_utc.strftime("%A"),
            "time_utc": now_utc.strftime("%Y-%m-%d %H:%M:%S UTC"),
            "time_sgt": _to_sgt(now_utc).strftime("%H:%M:%S SGT"),
            "n_domains": len(domains),
            "domains": domains,
        }
        return self._template.render(**ctx)
