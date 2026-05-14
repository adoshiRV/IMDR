"""FX domain extractors — BidFX tick fetching, bar building, and threading.

BidFX extractor uses `requests` with thread-local sessions (HTTPAdapter pooling,
basic auth). Other IMDR connectors use `httpx` (see connectors/http.py).
Both are acceptable — different use cases (threaded vs single-client).

CitiVelocity extractor is a stub for future implementation.
"""

from __future__ import annotations

import json
import statistics
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import structlog

from imdr.config.settings import Settings
from imdr.domains.fx.time_utils import HourWindow
from imdr.pipelines.extractors import APIExtractor
from imdr.universe.fx import FXUniverse

log = structlog.get_logger(__name__)

# Thread-local storage for requests sessions
_thread_local = threading.local()


def _get_session(username: str, password: str, timeout_connect: int, timeout_read: int) -> Any:
    """Get or create a thread-local requests.Session with basic auth."""
    if not hasattr(_thread_local, "session"):
        import requests
        from requests.adapters import HTTPAdapter

        session = requests.Session()
        session.auth = (username, password)
        adapter = HTTPAdapter(pool_connections=5, pool_maxsize=5, max_retries=2)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        _thread_local.session = session
        _thread_local.timeout = (timeout_connect, timeout_read)
    return _thread_local.session


# ---------------------------------------------------------------------------
# Tick extraction helpers (BidFX-specific)
# ---------------------------------------------------------------------------


def _num(x: Any) -> float | None:
    """Safely coerce a value to float."""
    if x is None:
        return None
    try:
        return float(x)
    except (ValueError, TypeError):
        return None


def spot_bid_ask(tick: dict[str, Any]) -> tuple[float | None, float | None]:
    """Extract spot bid/ask from a tick."""
    bid = _num(tick.get("bid_spot")) or _num(tick.get("bid"))
    ask = _num(tick.get("ask_spot")) or _num(tick.get("ask"))
    return bid, ask


def spot_mid(tick: dict[str, Any]) -> float | None:
    """Extract spot mid from a tick (average of bid/ask, with fallbacks)."""
    bid, ask = spot_bid_ask(tick)
    if bid is not None and ask is not None:
        return (bid + ask) / 2.0
    m = _num(tick.get("mid_spot"))
    if m is not None:
        return m
    return _num(tick.get("mid"))


def fwd_points_bid_ask(tick: dict[str, Any]) -> tuple[float | None, float | None]:
    """Extract forward points bid/ask from a tick."""
    bid = _num(tick.get("bid_forward_points"))
    ask = _num(tick.get("ask_forward_points"))
    return bid, ask


def outright_bid_ask_from_points(
    spot_bid: float, spot_ask: float,
    fwd_bid: float, fwd_ask: float,
) -> tuple[float, float]:
    """Calculate outright bid/ask from spot + forward points (direct addition)."""
    return spot_bid + fwd_bid, spot_ask + fwd_ask


def outright_mid_from_outright_bid_ask(bid: float, ask: float) -> float:
    """Calculate outright mid from outright bid/ask."""
    return (bid + ask) / 2.0


# ---------------------------------------------------------------------------
# Bar building
# ---------------------------------------------------------------------------


@dataclass
class BarDiagnostic:
    """Diagnostic info for a single bar build attempt."""

    symbol: str
    series: str
    reason: str = ""
    success: bool = True


def build_bar_from_ticks(
    ticks: list[dict[str, Any]],
    symbol_compact: str,
    series: str,
    tenor: str,
    deal_type: str,
    pair_used: str,
    ts: datetime,
    min_ticks: int = 1,
) -> tuple[dict[str, Any] | None, BarDiagnostic]:
    """Build an OHLC bar dict from a list of ticks.

    Returns (bar_dict, diagnostic). bar_dict is None if bar couldn't be built.
    The bar_dict uses `_px` suffixed field names matching [FX].[fact_ohlc].
    """
    diag = BarDiagnostic(symbol=symbol_compact, series=series)

    # Extract mids
    mids: list[float] = []
    bids: list[float] = []
    asks: list[float] = []

    for tick in ticks:
        if series == "SPOT":
            mid = spot_mid(tick)
            bid, ask = spot_bid_ask(tick)
        else:
            # Forward/NDF: need both spot and fwd points
            s_bid, s_ask = spot_bid_ask(tick)
            f_bid, f_ask = fwd_points_bid_ask(tick)
            if s_bid is None or s_ask is None or f_bid is None or f_ask is None:
                continue
            bid, ask = outright_bid_ask_from_points(s_bid, s_ask, f_bid, f_ask)
            mid = outright_mid_from_outright_bid_ask(bid, ask)

        if mid is not None:
            mids.append(mid)
        if bid is not None and ask is not None:
            bids.append(bid)
            asks.append(ask)

    if len(mids) < min_ticks:
        diag.success = False
        diag.reason = f"no_mids (got {len(mids)}, need {min_ticks})"
        return None, diag

    if not bids or not asks:
        diag.success = False
        diag.reason = "incomplete_exec_quote (no bid/ask)"
        return None, diag

    bar = {
        "ts": ts,
        "symbol": symbol_compact,
        "series": series,
        "tenor": tenor,
        "deal_type": deal_type,
        "pair_used": pair_used,
        "open_px": mids[0],
        "high_px": max(mids),
        "low_px": min(mids),
        "close_px": mids[-1],
        "mid_px": mids[-1],  # quote mid = last mid
        "mid_mean_px": statistics.mean(mids),
        "mid_median_px": statistics.median(mids),
        "bid": bids[-1],  # last bid
        "ask": asks[-1],  # last ask
        "n_ticks": len(mids),
    }
    return bar, diag


# ---------------------------------------------------------------------------
# Pair availability cache
# ---------------------------------------------------------------------------


@dataclass
class PairCache:
    """Persistent cache for pair availability (avoid repeated 404s)."""

    unavailable: dict[str, str] = field(default_factory=dict)  # pair -> expiry ISO
    _path: Path | None = None

    @classmethod
    def load(cls, path: Path) -> PairCache:
        cache = cls(_path=path)
        if path.exists():
            try:
                with open(path) as f:
                    data = json.load(f)
                cache.unavailable = data.get("unavailable", {})
            except Exception:
                log.warning("pair_cache_load_failed", path=str(path))
        return cache

    def save(self) -> None:
        if self._path is None:
            return
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._path, "w") as f:
            json.dump({"unavailable": self.unavailable}, f)

    def is_unavailable(self, pair: str, now: datetime) -> bool:
        expiry_str = self.unavailable.get(pair)
        if expiry_str is None:
            return False
        expiry = datetime.fromisoformat(expiry_str)
        if now >= expiry:
            del self.unavailable[pair]
            return False
        return True

    def mark_unavailable(self, pair: str, expiry: datetime) -> None:
        self.unavailable[pair] = expiry.isoformat()


# ---------------------------------------------------------------------------
# BidFX Extractor
# ---------------------------------------------------------------------------


class BidFXExtractor(APIExtractor[list[dict[str, Any]]]):
    """Fetch FX ticks from BidFX Historical Tick API and build OHLC bars.

    Uses thread-local `requests.Session` with basic auth for concurrent fetching.
    Returns list[dict] with `_px` suffixed field names matching [FX].[fact_ohlc].
    """

    def __init__(
        self,
        settings: Settings,
        universe: FXUniverse,
        window: HourWindow,
        pair_cache: PairCache | None = None,
        currencies: set[str] | None = None,
    ) -> None:
        super().__init__()
        self._settings = settings
        self._universe = universe
        self._window = window
        self._pair_cache = pair_cache or PairCache()
        self._currencies = currencies
        self._diagnostics: list[BarDiagnostic] = []

    @property
    def diagnostics(self) -> list[BarDiagnostic]:
        return self._diagnostics

    def extract(self) -> list[dict[str, Any]]:
        """Fetch ticks and build bars for all universe currencies.

        Work is dispatched per-currency (not per-series) so that non-G10
        currencies can derive both NDF_1M and SPOT bars from a single NDF fetch.
        """
        self._log.info(
            "bidfx_extract_start",
            window=str(self._window),
            symbols=len(self._universe.active_currencies),
        )

        bars: list[dict[str, Any]] = []
        self._diagnostics = []

        with ThreadPoolExecutor(max_workers=self._settings.bidfx_max_workers) as pool:
            futures = {
                pool.submit(self._process_currency, ccy): ccy
                for ccy in (self._currencies if self._currencies else self._universe.active_currencies)
            }

            for future in as_completed(futures):
                ccy = futures[future]
                try:
                    ccy_bars, ccy_diags = future.result()
                    self._diagnostics.extend(ccy_diags)
                    bars.extend(ccy_bars)
                except Exception:
                    self._log.exception("worker_failed", ccy=ccy)
                    series_list = self._universe.provider_series("bidfx", ccy)
                    for s in series_list:
                        self._diagnostics.append(BarDiagnostic(
                            symbol=ccy, series=s,
                            reason="worker_exception", success=False,
                        ))

        drops = [d for d in self._diagnostics if not d.success]
        self._log.info(
            "bidfx_extract_complete",
            bars=len(bars),
            drops=len(drops),
        )
        if drops:
            reason_counts: dict[str, int] = {}
            for d in drops:
                reason_counts[d.reason] = reason_counts.get(d.reason, 0) + 1
            self._log.info("bidfx_drop_summary", reasons=reason_counts)
            for d in drops:
                self._log.info(
                    "bidfx_drop_detail",
                    symbol=d.symbol, series=d.series, reason=d.reason,
                )
        return bars

    def _process_currency(
        self, ccy: str,
    ) -> tuple[list[dict[str, Any]], list[BarDiagnostic]]:
        """Fetch ticks and build bars for one currency.

        G10 / em_deliverable: separate SPOT + FORWARD fetches.
        em_ndf: single NDF fetch → NDF_1M bar (outright) + SPOT bar (spot fields).
        """
        bars: list[dict[str, Any]] = []
        diags: list[BarDiagnostic] = []
        series_list = self._universe.provider_series("bidfx", ccy)
        cls = self._universe.classification_for(ccy)

        base, quote = self._universe._order_pair(ccy, "USD")
        dotted = f"{base}.{quote}"

        if cls == "em_ndf":
            # Single NDF fetch → derive both NDF_1M and SPOT
            self._build_ndf_bars(dotted, series_list, bars, diags)
        else:
            # G10 / em_deliverable: separate fetch per series
            for series_name in series_list:
                self._build_single_bar(dotted, series_name, bars, diags)

        return bars, diags

    def _resolve_pair(
        self, dotted: str, series_name: str,
    ) -> str | None:
        """Find a non-cached candidate pair, or return None."""
        candidates = self._universe.candidates_for(dotted)
        now = self._window.start
        for candidate in candidates:
            if not self._pair_cache.is_unavailable(f"{candidate}:{series_name}", now):
                return candidate
        return None

    def _build_single_bar(
        self,
        dotted: str,
        series_name: str,
        bars: list[dict[str, Any]],
        diags: list[BarDiagnostic],
    ) -> None:
        """Fetch ticks for one series and build a single bar (G10 / em_deliverable)."""
        series_cfg = self._universe.series_config(series_name)
        compact = self._resolve_pair(dotted, series_name)
        if compact is None:
            diags.append(BarDiagnostic(
                symbol=dotted.replace(".", ""), series=series_name,
                reason="cached_unavailable", success=False,
            ))
            return

        ticks = self._fetch_ticks(compact, series_cfg.deal_type, series_cfg.tenor)
        if ticks is None:
            from datetime import timedelta
            self._pair_cache.mark_unavailable(
                f"{compact}:{series_name}", self._window.start + timedelta(days=7),
            )
            diags.append(BarDiagnostic(
                symbol=compact, series=series_name,
                reason="fetch_failed", success=False,
            ))
            return

        if not ticks:
            diags.append(BarDiagnostic(
                symbol=compact, series=series_name,
                reason="no_ticks_returned", success=False,
            ))
            return

        bar, diag = build_bar_from_ticks(
            ticks=ticks,
            symbol_compact=compact,
            series=series_name,
            tenor=series_cfg.tenor,
            deal_type=series_cfg.deal_type,
            pair_used=compact,
            ts=self._window.start,
        )
        diags.append(diag)
        if bar is not None:
            bars.append(bar)

    def _build_ndf_bars(
        self,
        dotted: str,
        series_list: list[str],
        bars: list[dict[str, Any]],
        diags: list[BarDiagnostic],
    ) -> None:
        """Single NDF fetch → build NDF_1M (outright) + SPOT (spot fields) bars."""
        ndf_cfg = self._universe.series_config("NDF_1M")
        compact = self._resolve_pair(dotted, "NDF_1M")
        if compact is None:
            for s in series_list:
                diags.append(BarDiagnostic(
                    symbol=dotted.replace(".", ""), series=s,
                    reason="cached_unavailable", success=False,
                ))
            return

        ticks = self._fetch_ticks(compact, ndf_cfg.deal_type, ndf_cfg.tenor)
        if ticks is None:
            from datetime import timedelta
            self._pair_cache.mark_unavailable(
                f"{compact}:NDF_1M", self._window.start + timedelta(days=7),
            )
            for s in series_list:
                diags.append(BarDiagnostic(
                    symbol=compact, series=s,
                    reason="fetch_failed", success=False,
                ))
            return

        if not ticks:
            for s in series_list:
                diags.append(BarDiagnostic(
                    symbol=compact, series=s,
                    reason="no_ticks_returned", success=False,
                ))
            return

        # NDF_1M bar (outright quotes)
        if "NDF_1M" in series_list:
            bar, diag = build_bar_from_ticks(
                ticks=ticks,
                symbol_compact=compact,
                series="NDF_1M",
                tenor=ndf_cfg.tenor,
                deal_type=ndf_cfg.deal_type,
                pair_used=compact,
                ts=self._window.start,
            )
            diags.append(diag)
            if bar is not None:
                bars.append(bar)

        # SPOT bar (spot fields from the same NDF tick stream)
        if "SPOT" in series_list:
            bar, diag = build_bar_from_ticks(
                ticks=ticks,
                symbol_compact=compact,
                series="SPOT",
                tenor="SPOT",
                deal_type="NDF",
                pair_used=compact,
                ts=self._window.start,
            )
            diags.append(diag)
            if bar is not None:
                bars.append(bar)

    def _fetch_ticks(
        self, pair: str, deal_type: str, tenor: str,
    ) -> list[dict[str, Any]] | None:
        """Fetch ticks from BidFX API for a single pair/deal_type/tenor."""
        session = _get_session(
            self._settings.bidfx_username,
            self._settings.bidfx_password,
            self._settings.bidfx_timeout_connect,
            self._settings.bidfx_timeout_read,
        )

        params = {
            "currency_pair": pair,
            "deal_type": deal_type,
            "tenor": tenor,
            "currency": pair[:3],
            "quantity": "1000000",
            "start_time": self._window.start.strftime("%Y%m%d%H%M%S"),
            "end_time": self._window.end.strftime("%Y%m%d%H%M%S"),
        }

        try:
            resp = session.get(
                self._settings.bidfx_base_url,
                params=params,
                timeout=_thread_local.timeout,
            )
            self._log.info(
                "bidfx_http_response",
                pair=pair, deal_type=deal_type, tenor=tenor,
                status=resp.status_code, length=len(resp.content),
            )
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            data = resp.json()
            # BidFX returns ticks under the "data" key
            ticks: list[dict[str, Any]] = []
            if isinstance(data, dict):
                dd = data.get("data")
                if isinstance(dd, list):
                    ticks = dd
            elif isinstance(data, list):
                ticks = data
            self._log.debug(
                "bidfx_ticks_parsed",
                pair=pair, deal_type=deal_type, tenor=tenor, n_ticks=len(ticks),
            )
            return ticks
        except Exception:
            self._log.warning(
                "fetch_ticks_failed", pair=pair, deal_type=deal_type,
                tenor=tenor, exc_info=True,
            )
            return None


# ---------------------------------------------------------------------------
# Legacy spot extractor aliases (kept for run_pipeline.py backward compat)
# ---------------------------------------------------------------------------


class FXSpotExtractor(APIExtractor[list[dict[str, Any]]]):
    """Legacy spot extractor — delegates to BidFX or CitiVelocity."""

    def __init__(self, provider: str, **kwargs: Any) -> None:
        super().__init__()
        self._provider = provider

    def extract(self) -> list[dict[str, Any]]:
        msg = f"{self._provider} spot extractor — use BidFXExtractor for OHLC"
        raise NotImplementedError(msg)


class CitiVelocityExtractor(APIExtractor[list[dict[str, Any]]]):
    """CitiVelocity extractor — stub for future implementation."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__()

    def extract(self) -> list[dict[str, Any]]:
        msg = "CitiVelocity API integration not yet configured."
        raise NotImplementedError(msg)
