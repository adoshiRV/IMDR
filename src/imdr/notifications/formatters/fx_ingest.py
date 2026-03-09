"""FX ingest email formatter — Jinja2 + inline CSS for professional Outlook emails."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader

_SGT = timezone(timedelta(hours=8))
_TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"


def _to_sgt(dt: datetime) -> datetime:
    """Convert a UTC datetime to SGT (UTC+8)."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(_SGT)


def _fmt_price(val: Any) -> str:
    """Format a price to 8 decimal places."""
    try:
        return f"{float(val):.8f}"
    except (ValueError, TypeError):
        return str(val)


def _spread_bps(bid: Any, ask: Any, mid: Any) -> str:
    """Compute spread in basis points: (ask - bid) / mid * 10000."""
    try:
        b, a, m = float(bid), float(ask), float(mid)
        if m == 0:
            return "—"
        return f"{(a - b) / m * 10000:.1f}"
    except (ValueError, TypeError, ZeroDivisionError):
        return "—"


def _prepare_bar_groups(bars: list[dict[str, Any]]) -> list[tuple[str, list[dict[str, Any]]]]:
    """Group bars by series, sort each group by symbol, add display fields."""
    series_order = ["SPOT", "FORWARD_1M", "NDF_1M"]
    groups: dict[str, list[dict[str, Any]]] = {}

    for bar in bars:
        series = bar.get("series", "UNKNOWN")
        row = {
            "symbol": bar.get("symbol", ""),
            "close_px": _fmt_price(bar.get("close_px")),
            "open_px": _fmt_price(bar.get("open_px")),
            "high_px": _fmt_price(bar.get("high_px")),
            "low_px": _fmt_price(bar.get("low_px")),
            "bid": _fmt_price(bar.get("bid")),
            "ask": _fmt_price(bar.get("ask")),
            "spread_bps": _spread_bps(bar.get("bid"), bar.get("ask"), bar.get("mid_px")),
            "n_ticks": bar.get("n_ticks", 0),
        }
        groups.setdefault(series, []).append(row)

    # Sort each group alphabetically by symbol
    for series in groups:
        groups[series].sort(key=lambda r: r["symbol"])

    # Return in canonical order, skip empty series
    result = []
    for s in series_order:
        if s in groups:
            result.append((s, groups[s]))
    # Any unexpected series at the end
    for s in sorted(groups):
        if s not in series_order:
            result.append((s, groups[s]))
    return result


class FXIngestFormatter:
    """Formats HTML emails for FX OHLC ingestion results."""

    def __init__(self) -> None:
        self._env = Environment(
            loader=FileSystemLoader(str(_TEMPLATE_DIR)),
            autoescape=True,
        )
        self._template = self._env.get_template("fx_ingest.html")

    def format_subject(
        self,
        pipeline_name: str = "",
        window_start: datetime | None = None,
        bars_approved: int = 0,
        bars_produced: int = 0,
        has_errors: bool = False,
        is_historical: bool = False,
        **kwargs: Any,
    ) -> str:
        mode = "Historical" if is_historical else "Live"
        status = "ERROR" if has_errors else "OK"
        if window_start:
            utc_str = window_start.strftime("%Y-%m-%d %H:%M")
            sgt_str = _to_sgt(window_start).strftime("%H:%M")
        else:
            utc_str = "N/A"
            sgt_str = "N/A"
        return f"[IMDR] FX {mode} Ingest {status} | {utc_str} UTC ({sgt_str} SGT) | {bars_approved}/{bars_produced} bars"

    def format_body(
        self,
        pipeline_name: str = "",
        window_start: datetime | None = None,
        window_end: datetime | None = None,
        bars_produced: int = 0,
        bars_approved: int = 0,
        bars_dropped: int = 0,
        bars: list[dict[str, Any]] | None = None,
        missing_ccy: list[str] | None = None,
        holiday_hits: list[dict[str, str]] | None = None,
        anomalies: list[dict[str, Any]] | None = None,
        diagnostics: list[dict[str, Any]] | None = None,
        elapsed_secs: float = 0.0,
        n_symbols: int = 0,
        is_historical: bool = False,
        **kwargs: Any,
    ) -> str:
        bars = bars or []
        missing_ccy = missing_ccy or []
        holiday_hits = holiday_hits or []
        anomalies = anomalies or []
        diagnostics = diagnostics or []

        now_utc = datetime.now(timezone.utc)

        # Window strings (UTC + SGT)
        if window_start and window_end:
            ws_utc = window_start.strftime("%Y-%m-%d %H:%M")
            we_utc = window_end.strftime("%H:%M")
            ws_sgt = _to_sgt(window_start).strftime("%H:%M")
            we_sgt = _to_sgt(window_end).strftime("%H:%M")
            window_utc = f"{ws_utc}\u2013{we_utc} UTC"
            window_sgt = f"{ws_sgt}\u2013{we_sgt} SGT"
        else:
            window_utc = "N/A"
            window_sgt = "N/A"

        # Run time strings
        run_time_utc = now_utc.strftime("%Y-%m-%d %H:%M:%S UTC")
        run_time_sgt = _to_sgt(now_utc).strftime("%H:%M:%S SGT")

        # Elapsed
        elapsed = f"{elapsed_secs:.1f}s" if elapsed_secs else "N/A"

        # Bar groups
        bar_groups = _prepare_bar_groups(bars)

        ctx = {
            "mode": "Historical" if is_historical else "Live",
            "has_errors": any(d.get("reason") for d in diagnostics) or bars_dropped > 0,
            "pipeline_name": pipeline_name,
            "window_utc": window_utc,
            "window_sgt": window_sgt,
            "run_time_utc": run_time_utc,
            "run_time_sgt": run_time_sgt,
            "elapsed": elapsed,
            "n_symbols": n_symbols,
            "bars_produced": bars_produced,
            "bars_approved": bars_approved,
            "bars_dropped": bars_dropped,
            "n_missing": len(missing_ccy),
            "n_anomalies": len(anomalies),
            "n_holidays": len(holiday_hits),
            "bar_groups": bar_groups,
            "anomalies": anomalies,
            "diagnostics": diagnostics,
            "missing_ccy": missing_ccy,
            "holiday_hits": holiday_hits,
        }
        return self._template.render(**ctx)
