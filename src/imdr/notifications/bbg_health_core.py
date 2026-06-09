"""Shared core for BBG end-of-day health checks (FX + rates).

Both ``scripts/bbg_fx_health_check.py`` and
``scripts/bbg_rates_health_check.py`` share most of their machinery:
constants, the bbgCheck heartbeat scanner, the per-batch UTC-hour
bucket map, the per-item dataclass, and the HTML / console renderers.

This module owns those pieces. Each domain script supplies only:

* a noun ("pair" / "curve"),
* a SQL query that returns one :class:`ItemStatus` per item,
* a universe-size source,
* a domain-specific known-broken set,
* (optional) a domain-specific extra-section builder (FX has a
  DAILY-cadence coverage table; rates doesn't).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, timedelta, timezone
from pathlib import Path

BBG_CHECK_DIR = Path(
    r"Z:\Business\Research\Dashboard\DataSources\BBG_mirror\log\bbgCheck"
)
EXPECTED_BATCHES_PER_DAY = 6
SGT = timezone(timedelta(hours=8))

# UTC hour each BBG batch lands in. mtime always falls within ±30 min of the
# batch wall-clock; bucketing by UTC hour cleanly identifies which batch a
# row belongs to.
BATCH_LABELS: dict[int, str] = {
    1: "09:30 SGT",   # 01:30 UTC — Asia open
    3: "11:00 SGT",   # 03:00 UTC — Asia mid
    5: "13:00 SGT",   # 05:00 UTC — Asia lunch
    8: "16:00 SGT",   # 08:00 UTC — SGT close
    10: "18:00 SGT",  # 10:00 UTC — LDN morning
    11: "19:00 SGT",  # 11:00 UTC — LDN early afternoon (last fire)
}

# bbgCheck filename pattern: [YYYY-MM-DD HHhMMmSSs][user][V=value].csv
# value is "NA" (failure) or a numeric LAST_PRICE (success).
_BBGCHECK_RE = re.compile(
    r"\[(?P<dt>\d{4}-\d{2}-\d{2} \d{2}h\d{2}m\d{2}(?:\.\d+)?s)\]"
    r"\[(?P<user>[^\]]+)\]"
    r"\[V=(?P<value>[^\]]+)\]\.csv"
)


@dataclass
class ItemStatus:
    """Per-item snapshot count + which UTC hours showed up.

    Used uniformly for both pairs (FX) and curves (rates) — caller picks
    the noun via the ``label`` field's content (e.g. ``"USD/JPY"`` or
    ``"AUD/BBSW_3M"``).
    """
    label: str
    rows: int = 0
    captured_hours_utc: list[int] = field(default_factory=list)
    is_known_broken: bool = False

    @property
    def batches_captured(self) -> int:
        return len(set(self.captured_hours_utc))

    @property
    def is_ok(self) -> bool:
        return self.batches_captured >= EXPECTED_BATCHES_PER_DAY

    @property
    def missing_batches(self) -> list[str]:
        captured = set(self.captured_hours_utc)
        return [label for hour, label in BATCH_LABELS.items()
                if hour not in captured]


@dataclass
class BBGCheckSummary:
    """Heartbeat summary scanned out of ``log/bbgCheck/``."""
    total: int = 0
    successes: int = 0
    failures: int = 0  # V=NA
    failure_times_sgt: list[str] = field(default_factory=list)


def scan_bbg_check_log(target_date: date) -> BBGCheckSummary:
    """Scan ``Z:\\BBG_mirror\\log\\bbgCheck\\*.csv`` for the target date.

    The bbgCheck log is shared across all BBG domains — filename has
    ``[V=NA]`` when the terminal was offline regardless of which feed
    was about to read.
    """
    summary = BBGCheckSummary()
    if not BBG_CHECK_DIR.exists():
        return summary

    target_prefix = f"[{target_date.isoformat()} "
    for path in BBG_CHECK_DIR.iterdir():
        name = path.name
        if not name.startswith(target_prefix):
            continue
        m = _BBGCHECK_RE.match(name)
        if not m:
            continue
        summary.total += 1
        if m.group("value").upper() == "NA":
            summary.failures += 1
            summary.failure_times_sgt.append(
                m.group("dt").replace("h", ":").replace("m", ":").replace("s", "")
            )
        else:
            summary.successes += 1
    return summary


@dataclass
class HealthReport:
    """Aggregated counts derived from a list of :class:`ItemStatus`."""
    actionable_universe: int
    n_ok: int
    n_partial: int
    n_missing: int
    rows_total: int
    has_problem: bool


def summarize(items: list[ItemStatus], universe_size: int,
              known_broken: set[str], bbg_check: BBGCheckSummary,
              extra_problem: bool = False) -> HealthReport:
    actionable = [it for it in items if not it.is_known_broken]
    n_ok = sum(1 for it in actionable if it.is_ok)
    n_partial = sum(
        1 for it in actionable
        if 0 < it.batches_captured < EXPECTED_BATCHES_PER_DAY
    )
    actionable_universe = universe_size - len(known_broken)
    n_missing = actionable_universe - len(actionable)
    rows_total = sum(it.rows for it in items)
    has_problem = (n_partial > 0 or n_missing > 0
                   or bbg_check.failures > 0 or extra_problem)
    return HealthReport(
        actionable_universe=actionable_universe,
        n_ok=n_ok,
        n_partial=n_partial,
        n_missing=n_missing,
        rows_total=rows_total,
        has_problem=has_problem,
    )


def build_html(
    *,
    noun: str,                    # "pair" / "curve"
    domain_label: str,            # "FX" / "rates"
    target_date: date,
    items: list[ItemStatus],
    bbg_check: BBGCheckSummary,
    report: HealthReport,
    source_path_hint: str,
    pipeline_hint: str,
    extra_html: str = "",
) -> str:
    """Render the standard BBG health-check email body.

    ``extra_html`` lets the caller append a domain-specific section
    (e.g. FX's DAILY coverage table) before the footer.
    """
    status_color = "#d9534f" if report.has_problem else "#5cb85c"
    status_text = "ATTENTION" if report.has_problem else "OK"
    Noun = noun.capitalize()
    body = f"""
    <html><body style="font-family: Calibri, Arial, sans-serif; font-size: 11pt;">
    <h2 style="color: {status_color};">BBG {domain_label} SNAPSHOT Health Check — {status_text}</h2>
    <p><b>Date:</b> {target_date.isoformat()}<br>
       <b>{Noun}s OK ({EXPECTED_BATCHES_PER_DAY}/{EXPECTED_BATCHES_PER_DAY} batches):</b> {report.n_ok} / {report.actionable_universe}<br>
       <b>{Noun}s partial:</b> {report.n_partial}<br>
       <b>{Noun}s missing entirely:</b> {report.n_missing}<br>
       <b>Total rows captured:</b> {report.rows_total:,}</p>

    <h3>Upstream BBG terminal status (from bbgCheck/)</h3>
    <p><b>Heartbeats:</b> {bbg_check.total} total, {bbg_check.successes} success, {bbg_check.failures} failed (V=NA)</p>
    """
    if bbg_check.failures:
        body += (
            f'<p style="color: #d9534f;"><b>BBG terminal was offline at:</b> '
            f"{', '.join(bbg_check.failure_times_sgt)} — these missed batches "
            "are NOT our ingest fault.</p>"
        )

    body += f"<h3>Per-{noun} detail</h3>"
    body += "<table border='1' cellpadding='6' cellspacing='0'>"
    body += (f"<tr><th>{Noun}</th><th>Batches</th><th>Rows</th>"
             "<th>Missing batches</th><th>Status</th></tr>")
    for it in items:
        if it.is_known_broken:
            color, status = "#999999", "KNOWN BROKEN"
        elif it.is_ok:
            color, status = "#5cb85c", "OK"
        else:
            color, status = "#f0ad4e", "PARTIAL"
        missing_html = ", ".join(it.missing_batches) if it.missing_batches else "-"
        body += (
            f"<tr><td>{it.label}</td>"
            f"<td>{it.batches_captured} / {EXPECTED_BATCHES_PER_DAY}</td>"
            f"<td>{it.rows}</td>"
            f"<td>{missing_html}</td>"
            f"<td style='color: {color};'>{status}</td></tr>"
        )
    body += "</table>"

    if extra_html:
        body += extra_html

    body += (
        f"<p><i>Pipeline: <code>{pipeline_hint}</code>. "
        f"Source: <code>{source_path_hint}</code>.</i></p>"
        "</body></html>"
    )
    return body


def print_console(
    *,
    noun: str,
    domain_label: str,
    target_date: date,
    items: list[ItemStatus],
    bbg_check: BBGCheckSummary,
    report: HealthReport,
    label_width: int = 22,
    extra_lines: list[str] | None = None,
) -> None:
    """Pretty-print the standard BBG health-check console output."""
    Noun = noun.capitalize()
    print(f"\nBBG {domain_label} SNAPSHOT health check — {target_date.isoformat()}",
          flush=True)
    print("=" * 100, flush=True)
    print(f"BBG bbgCheck heartbeats: {bbg_check.total} total, "
          f"{bbg_check.successes} OK, {bbg_check.failures} V=NA (terminal offline)",
          flush=True)
    if bbg_check.failures:
        print(f"  Failed times (SGT): {bbg_check.failure_times_sgt}", flush=True)
    print(f"\nPer-{noun} detail (expected {EXPECTED_BATCHES_PER_DAY} batches each):",
          flush=True)
    print(f"  {Noun:<{label_width}} {'Batches':>8} {'Rows':>6}  "
          f"{'Missing':<42} {'Status':>12}", flush=True)
    for it in items:
        if it.is_known_broken:
            status = "KNOWN-BROKEN"
        elif it.is_ok:
            status = "OK"
        else:
            status = "PARTIAL"
        missing = ", ".join(it.missing_batches) if it.missing_batches else "-"
        print(f"  {it.label:<{label_width}} "
              f"{it.batches_captured:>4}/{EXPECTED_BATCHES_PER_DAY:<3} "
              f"{it.rows:>6}  {missing:<42} {status:>12}", flush=True)
    if report.n_missing:
        print(f"\n  WARNING: {report.n_missing} expected {noun}s captured zero batches",
              flush=True)
    if extra_lines:
        for line in extra_lines:
            print(line, flush=True)
    print("=" * 100, flush=True)


def build_subject(
    *,
    domain_label: str,
    target_date: date,
    report: HealthReport,
    bbg_check: BBGCheckSummary,
    extra_segments: list[str] | None = None,
) -> str:
    """Standard subject: ``[OK]/[!] BBG {domain} Health | {date} | N/M full[, ...]``."""
    status_icon = "[!]" if report.has_problem else "[OK]"
    parts = [f"{report.n_ok}/{report.actionable_universe} full"]
    if report.n_partial:
        parts.append(f"{report.n_partial} partial")
    if report.n_missing:
        parts.append(f"{report.n_missing} missing")
    if extra_segments:
        parts.extend(extra_segments)
    if bbg_check.failures:
        parts.append(f"{bbg_check.failures} BBG offline")
    return (
        f"{status_icon} BBG {domain_label} Health | {target_date.isoformat()} | "
        + ", ".join(parts)
    )
