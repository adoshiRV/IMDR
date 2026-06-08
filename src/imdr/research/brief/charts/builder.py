"""Build the full chart set for a brief.

This is a thin orchestrator — each ``chart_*`` function below is
self-contained and writes one PNG. Designed so new chart types can be
added without touching the orchestrator.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Connection

from .base import RV_PALETTE as P
from .base import configure_matplotlib, style_axes


def _save(fig, out_dir: Path, name: str) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    p = out_dir / name
    fig.tight_layout()
    fig.savefig(p)
    plt.close(fig)
    return p


def _annotate_last(ax, x, y, fmt: str = "{:.2f}", color: str | None = None) -> None:
    c = color or P.accent
    ax.scatter([x], [y], color=c, zorder=5, s=22)
    ax.annotate(fmt.format(y), xy=(x, y), xytext=(8, 6),
                textcoords="offset points", color=c,
                fontsize=10.5, fontweight="semibold")


# ----------------------------------------------------------------- FX
def _fx_series(cx: Connection, base: str, quote: str, start: str) -> pd.DataFrame:
    df = pd.read_sql(text("""
        SELECT r.obs_ts AS ts, CAST(r.mid_rate AS float) AS value
        FROM fx.fact_fx_rate r
        JOIN fx.dim_currency_pair p ON p.id = r.pair_id
        WHERE p.base_ccy=:b AND p.quote_ccy=:q AND r.tenor='SPOT'
          AND r.obs_ts >= :start
        ORDER BY r.obs_ts
    """), cx, params={"b": base, "q": quote, "start": start})
    df["ts"] = pd.to_datetime(df["ts"], utc=True)
    return df.set_index("ts")


def chart_eurusd(cx: Connection, out_dir: Path, *, eur_eoy_target: float | None = 1.14) -> Path:
    df = _fx_series(cx, "EUR", "USD", "2026-04-01")
    fig, ax = plt.subplots()
    ax.plot(df.index, df["value"], color=P.accent, lw=1.7)
    _annotate_last(ax, df.index[-1], df["value"].iloc[-1], "{:.4f}")
    if eur_eoy_target:
        ax.axhline(eur_eoy_target, color=P.warn, lw=1.0, ls="--", alpha=0.7)
        ax.annotate(f"UBS EOY target {eur_eoy_target:.2f}", xy=(df.index[5], eur_eoy_target),
                    xytext=(0, 3), textcoords="offset points",
                    fontsize=9.5, color=P.warn, fontweight="semibold")
    ax.set_title("EUR/USD — into the ECB hike")
    ax.set_ylabel("EURUSD")
    ax.xaxis.set_major_locator(mdates.MonthLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b"))
    style_axes(ax)
    return _save(fig, out_dir, "fx_eurusd.png")


def chart_usdjpy(cx: Connection, out_dir: Path) -> Path:
    df = _fx_series(cx, "USD", "JPY", "2026-04-01")
    fig, ax = plt.subplots()
    ax.plot(df.index, df["value"], color=P.accent, lw=1.7)
    _annotate_last(ax, df.index[-1], df["value"].iloc[-1])
    ax.axhline(160.0, color=P.neg, lw=1.2, alpha=0.65)
    ax.annotate("MoF intervention line 160", xy=(df.index[5], 160.0),
                xytext=(0, 4), textcoords="offset points",
                fontsize=9.5, color=P.neg, fontweight="semibold")
    ax.axhline(162.0, color=P.warn, lw=1.0, ls="--", alpha=0.7)
    ax.annotate("UBS target 162", xy=(df.index[5], 162.0),
                xytext=(0, 4), textcoords="offset points",
                fontsize=9.5, color=P.warn, fontweight="semibold")
    ax.set_title("USD/JPY — at MoF intervention line; UBS targets 162")
    ax.set_ylabel("USDJPY")
    ax.xaxis.set_major_locator(mdates.MonthLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b"))
    style_axes(ax)
    return _save(fig, out_dir, "fx_usdjpy.png")


def chart_usdkrw(cx: Connection, out_dir: Path,
                 *, eoy_target: float = 1450, add_zone: tuple[float, float] = (1480, 1500)) -> Path:
    df = _fx_series(cx, "USD", "KRW", "2026-04-01")
    fig, ax = plt.subplots()
    ax.plot(df.index, df["value"], color=P.neg, lw=1.7)
    _annotate_last(ax, df.index[-1], df["value"].iloc[-1], "{:.0f}", P.neg)
    ax.axhline(eoy_target, color=P.pos, lw=1.0, ls="--", alpha=0.7)
    ax.annotate(f"HSBC EOY target {eoy_target:.0f}",
                xy=(df.index[5], eoy_target),
                xytext=(0, -14), textcoords="offset points",
                fontsize=9.5, color=P.pos, fontweight="semibold")
    ax.axhspan(add_zone[0], add_zone[1], color=P.light_green, alpha=0.18)
    ax.annotate(f"HSBC/Citi/Nomura add zone {add_zone[0]:.0f}-{add_zone[1]:.0f}",
                xy=(df.index[5], sum(add_zone) / 2),
                xytext=(0, 0), textcoords="offset points",
                fontsize=9, color=P.pos, fontweight="semibold")
    ax.set_title("USD/KRW — worst EM, foreign equity outflows")
    ax.set_ylabel("USDKRW")
    ax.xaxis.set_major_locator(mdates.MonthLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b"))
    style_axes(ax)
    return _save(fig, out_dir, "fx_usdkrw.png")


def chart_usdcad(cx: Connection, out_dir: Path,
                 *, range_band: tuple[float, float] = (1.385, 1.400)) -> Path:
    df = _fx_series(cx, "USD", "CAD", "2026-04-01")
    fig, ax = plt.subplots()
    ax.plot(df.index, df["value"], color=P.accent, lw=1.7)
    _annotate_last(ax, df.index[-1], df["value"].iloc[-1], "{:.4f}")
    ax.axhspan(range_band[0], range_band[1], color=P.light_green, alpha=0.15)
    ax.annotate(f"Range-trade band {range_band[0]:.3f} / {range_band[1]:.3f}",
                xy=(df.index[5], sum(range_band) / 2),
                xytext=(0, 0), textcoords="offset points",
                fontsize=9.5, color=P.pos, fontweight="semibold")
    ax.set_title("USD/CAD — BoC hold priced; range-bound")
    ax.set_ylabel("USDCAD")
    ax.xaxis.set_major_locator(mdates.MonthLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b"))
    style_axes(ax)
    return _save(fig, out_dir, "fx_usdcad.png")


# ----------------------------------------------------------------- UST
def chart_ust_curve(cx: Connection, out_dir: Path, *, title: str = "UST curve YTD") -> Path:
    df = pd.read_sql(text("""
        SELECT i.source_code AS code, f.obs_date, f.value
        FROM econ.fact_indicator f JOIN econ.dim_indicator i ON i.id=f.indicator_id
        WHERE i.source_code IN ('DGS2','DGS5','DGS10','DGS30') AND f.obs_date >= '2026-01-01'
        ORDER BY f.obs_date
    """), cx)
    df["obs_date"] = pd.to_datetime(df["obs_date"])
    pv = df.pivot(index="obs_date", columns="code", values="value").sort_index()
    fig, ax = plt.subplots()
    colors = {"DGS2": P.accent, "DGS5": P.light_green, "DGS10": P.neg, "DGS30": P.warn}
    labels = {"DGS2": "UST 2y", "DGS5": "UST 5y", "DGS10": "UST 10y", "DGS30": "UST 30y"}
    for col in ["DGS2", "DGS5", "DGS10", "DGS30"]:
        if col not in pv.columns:
            continue
        ax.plot(pv.index, pv[col], color=colors[col], lw=1.5, label=labels[col])
        last_d = pv[col].dropna().index[-1]
        last_v = pv[col].dropna().iloc[-1]
        ax.annotate(f"{last_v:.2f}", xy=(last_d, last_v), xytext=(4, 0),
                    textcoords="offset points", color=colors[col],
                    fontsize=9.5, fontweight="semibold", va="center")
    ax.set_title(title)
    ax.set_ylabel("Yield (%)")
    ax.legend(loc="lower center", ncol=4, bbox_to_anchor=(0.5, -0.18))
    ax.xaxis.set_major_locator(mdates.MonthLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b"))
    style_axes(ax)
    return _save(fig, out_dir, "ust_curve_ytd.png")


def chart_ust_2s10s(cx: Connection, out_dir: Path) -> Path:
    df = pd.read_sql(text("""
        SELECT i.source_code AS code, f.obs_date, f.value
        FROM econ.fact_indicator f JOIN econ.dim_indicator i ON i.id=f.indicator_id
        WHERE i.source_code IN ('DGS2','DGS10') AND f.obs_date >= '2026-01-01'
        ORDER BY f.obs_date
    """), cx)
    df["obs_date"] = pd.to_datetime(df["obs_date"])
    pv = df.pivot(index="obs_date", columns="code", values="value").dropna()
    pv["spread_bp"] = (pv["DGS10"] - pv["DGS2"]) * 100
    fig, ax = plt.subplots()
    ax.plot(pv.index, pv["spread_bp"], color=P.accent, lw=1.7)
    _annotate_last(ax, pv.index[-1], pv["spread_bp"].iloc[-1], "{:.0f} bp")
    ax.axhline(0, color=P.muted, lw=0.7, ls="--", alpha=0.7)
    ax.set_title("UST 2s10s spread YTD")
    ax.set_ylabel("10y − 2y (bp)")
    ax.xaxis.set_major_locator(mdates.MonthLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b"))
    style_axes(ax)
    return _save(fig, out_dir, "ust_2s10s.png")


# ----------------------------------------------------------------- CPI
def chart_us_cpi_yoy(cx: Connection, out_dir: Path, *, consensus_mid: float | None = None,
                     consensus_range: float = 0.05) -> Path:
    df = pd.read_sql(text("""
        SELECT f.obs_date, f.value FROM econ.fact_indicator f
        JOIN econ.dim_indicator i ON i.id=f.indicator_id
        WHERE i.source_code='CPIAUCSL' AND f.obs_date >= '2023-01-01'
        ORDER BY f.obs_date
    """), cx)
    df["obs_date"] = pd.to_datetime(df["obs_date"])
    df = df.dropna(subset=["value"]).set_index("obs_date").sort_index()
    yago = df["value"].reindex(df.index - pd.DateOffset(years=1))
    yago.index = df.index
    df["yoy"] = (df["value"] / yago - 1) * 100
    df = df.dropna(subset=["yoy"]).reset_index()
    fig, ax = plt.subplots(figsize=(11, 5.2))
    ax.plot(df["obs_date"], df["yoy"], color=P.neg, lw=1.9)
    last = df.iloc[-1]
    ax.scatter([last["obs_date"]], [last["yoy"]], color=P.neg, zorder=5, s=34)
    ax.annotate(f"{last['obs_date']:%b-%y} · {last['yoy']:.2f}%",
                xy=(last["obs_date"], last["yoy"]),
                xytext=(-14, -22), textcoords="offset points",
                color=P.neg, fontweight="semibold", fontsize=11, ha="right")
    if consensus_mid:
        nxt = last["obs_date"] + pd.offsets.MonthEnd(1)
        ax.errorbar([nxt], [consensus_mid],
                    yerr=[[consensus_range], [consensus_range]],
                    fmt="X", color=P.warn, markersize=11, capsize=6, lw=1.6, zorder=5)
        ax.annotate(f"Next-month consensus\n{consensus_mid-consensus_range:.2f}-{consensus_mid+consensus_range:.2f}%",
                    xy=(nxt, consensus_mid), xytext=(14, 2),
                    textcoords="offset points", color=P.warn,
                    fontweight="semibold", fontsize=10.5, ha="left", va="center")
        ax.set_xlim(df["obs_date"].iloc[0], nxt + pd.Timedelta(days=60))
    ax.axhline(2.0, color=P.pos, lw=1.0, ls="--", alpha=0.7)
    ax.annotate("Fed target 2%", xy=(df["obs_date"].iloc[2], 2.0),
                xytext=(0, 4), textcoords="offset points",
                fontsize=10, color=P.pos, fontweight="semibold")
    ax.set_title(f"US Headline CPI YoY — {last['obs_date']:%b-%y} latest {last['yoy']:.2f}%", pad=18)
    ax.set_ylabel("CPI YoY %")
    style_axes(ax)
    return _save(fig, out_dir, "us_cpi_yoy.png")


# ----------------------------------------------------------------- Commodities + VIX + Equities
def chart_oil_gold(cx: Connection, out_dir: Path) -> Path:
    df = pd.read_sql(text("""
        SELECT c.symbol, s.obs_date, s.price FROM commodities.fact_spot s
        JOIN commodities.dim_commodity c ON c.id=s.commodity_id
        WHERE c.symbol IN ('CR_NYM_CL','XAU') AND s.obs_date >= '2026-01-01'
        ORDER BY s.obs_date
    """), cx)
    df["obs_date"] = pd.to_datetime(df["obs_date"])
    fig, ax1 = plt.subplots()
    wti = df[df["symbol"] == "CR_NYM_CL"]
    ax1.plot(wti["obs_date"], wti["price"], color=P.warn, lw=1.8, label="WTI ($/bbl, lhs)")
    ax1.set_ylabel("WTI USD/bbl", color=P.warn)
    last_w = wti.iloc[-1]
    ax1.annotate(f"WTI ${last_w['price']:.1f}",
                 xy=(last_w["obs_date"], last_w["price"]),
                 xytext=(8, 6), textcoords="offset points",
                 color=P.warn, fontweight="semibold", fontsize=10.5)
    ax2 = ax1.twinx()
    ax2.spines["top"].set_visible(False)
    gold = df[df["symbol"] == "XAU"]
    ax2.plot(gold["obs_date"], gold["price"], color=P.accent, lw=1.4,
             label="Gold ($/oz, rhs)", alpha=0.85)
    ax2.set_ylabel("Gold USD/oz", color=P.accent)
    last_g = gold.iloc[-1]
    ax2.annotate(f"Gold ${last_g['price']:.0f}",
                 xy=(last_g["obs_date"], last_g["price"]),
                 xytext=(8, -14), textcoords="offset points",
                 color=P.accent, fontweight="semibold", fontsize=10.5)
    ax2.grid(False)
    ax2.tick_params(length=0)
    ax1.set_title("WTI crude + Gold YTD — Iran/Hormuz premium")
    ax1.xaxis.set_major_locator(mdates.MonthLocator())
    ax1.xaxis.set_major_formatter(mdates.DateFormatter("%b"))
    lns1, lbs1 = ax1.get_legend_handles_labels()
    lns2, lbs2 = ax2.get_legend_handles_labels()
    ax1.legend(lns1 + lns2, lbs1 + lbs2, loc="upper left")
    style_axes(ax1)
    return _save(fig, out_dir, "oil_gold_ytd.png")


def chart_vix(cx: Connection, out_dir: Path) -> Path:
    raw = pd.read_sql(text("""
        SELECT ticker, obs_date, close_level FROM equities.fact_vix
        WHERE obs_date >= '2026-04-01' AND ticker IN ('VIX','VIX9D','VIX3M')
        ORDER BY obs_date
    """), cx)
    raw["obs_date"] = pd.to_datetime(raw["obs_date"])
    df = raw.pivot(index="obs_date", columns="ticker", values="close_level").sort_index()
    fig, ax = plt.subplots()
    colors = {"VIX": P.accent, "VIX9D": P.neg, "VIX3M": P.warn}
    for col in ["VIX", "VIX9D", "VIX3M"]:
        if col not in df.columns:
            continue
        ax.plot(df.index, df[col], lw=1.7 if col == "VIX" else 1.3,
                color=colors[col], label=col, alpha=0.95 if col == "VIX" else 0.85)
    ax.axhline(20, color=P.muted, lw=0.8, ls=":", alpha=0.6)
    ax.set_title("CBOE Vol Indices")
    ax.set_ylabel("Index level")
    ax.legend(loc="upper left")
    ax.xaxis.set_major_locator(mdates.MonthLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b"))
    style_axes(ax)
    return _save(fig, out_dir, "vix_term.png")


def chart_equity_rebased(cx: Connection, out_dir: Path) -> Path:
    tickers = [
        ("SPX", "S&P 500", P.accent),
        ("STOXX50E", "Euro Stoxx 50", P.neg),
        ("N225", "Nikkei 225", P.pos),
        ("KS200", "KOSPI 200", P.warn),
        ("NSEI", "Nifty 50", P.light_green),
    ]
    fig, ax = plt.subplots(figsize=(11, 5.0))
    for t, name, col in tickers:
        df = pd.read_sql(text("""
            SELECT f.obs_date, f.close_level FROM equities.fact_index_level f
            JOIN equities.dim_index i ON i.id=f.index_id
            WHERE i.ticker=:t AND f.obs_date >= '2026-04-01'
            ORDER BY f.obs_date
        """), cx, params={"t": t})
        if df.empty:
            continue
        df["obs_date"] = pd.to_datetime(df["obs_date"])
        base_v = df["close_level"].iloc[0]
        y = (df["close_level"] / base_v - 1) * 100
        ax.plot(df["obs_date"], y, lw=1.5, color=col, label=name)
        ax.annotate(f"{y.iloc[-1]:+.1f}%",
                    xy=(df["obs_date"].iloc[-1], y.iloc[-1]),
                    xytext=(6, 0), textcoords="offset points",
                    color=col, fontsize=9.5, fontweight="semibold", va="center")
    ax.axhline(0, color=P.muted, lw=0.6)
    ax.set_title("Major equity indices — rebased to 1 Apr 2026 (% chg)")
    ax.set_ylabel("% vs 1-Apr-2026")
    ax.legend(loc="lower left", ncol=3)
    ax.xaxis.set_major_locator(mdates.MonthLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b"))
    style_axes(ax)
    return _save(fig, out_dir, "equity_rebased.png")


# ----------------------------------------------------------------- orchestrator
def build_all_charts(
    cx: Connection,
    out_dir: Path,
    *,
    include_eurusd: bool = True,
    include_usdjpy: bool = True,
    include_usdkrw: bool = True,
    include_usdcad: bool = True,
    include_ust_curve: bool = True,
    include_ust_2s10s: bool = True,
    include_us_cpi: bool = True,
    cpi_consensus_mid: float | None = None,
    include_oil_gold: bool = True,
    include_vix: bool = True,
    include_equity: bool = True,
) -> list[Path]:
    """Generate the full standard chart set. Returns list of written paths."""
    configure_matplotlib()
    paths: list[Path] = []
    if include_eurusd:    paths.append(chart_eurusd(cx, out_dir))
    if include_usdjpy:    paths.append(chart_usdjpy(cx, out_dir))
    if include_usdkrw:    paths.append(chart_usdkrw(cx, out_dir))
    if include_usdcad:    paths.append(chart_usdcad(cx, out_dir))
    if include_ust_curve: paths.append(chart_ust_curve(cx, out_dir))
    if include_ust_2s10s: paths.append(chart_ust_2s10s(cx, out_dir))
    if include_us_cpi:    paths.append(chart_us_cpi_yoy(cx, out_dir, consensus_mid=cpi_consensus_mid))
    if include_oil_gold:  paths.append(chart_oil_gold(cx, out_dir))
    if include_vix:       paths.append(chart_vix(cx, out_dir))
    if include_equity:    paths.append(chart_equity_rebased(cx, out_dir))
    return paths
