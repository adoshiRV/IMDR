"""Shared matplotlib configuration + RV palette tokens for all charts."""
from __future__ import annotations

from dataclasses import dataclass

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


@dataclass(frozen=True)
class Palette:
    bg: str = "#FFFFFF"
    panel: str = "#F4F1EA"
    panel_2: str = "#FAF8F2"
    fg: str = "#3D3E3E"
    muted: str = "#8A8B8B"
    border: str = "#DDD8CC"
    border_soft: str = "#ECE8DE"
    accent: str = "#004527"
    pos: str = "#1F7D4A"
    neg: str = "#8B2E1E"
    warn: str = "#B58A2C"
    light_green: str = "#6FA77E"


RV_PALETTE = Palette()


def configure_matplotlib() -> None:
    """Apply RV-Capital matplotlib defaults. Idempotent — safe to call twice."""
    plt.rcParams.update({
        "figure.figsize": (10.5, 5.0),
        "figure.dpi": 160,
        "figure.facecolor": RV_PALETTE.bg,
        "savefig.facecolor": RV_PALETTE.bg,
        "savefig.bbox": "tight",
        "savefig.dpi": 160,
        "font.family": "DejaVu Sans",
        "font.size": 11.5,
        "axes.titlesize": 13,
        "axes.titleweight": "semibold",
        "axes.titlecolor": RV_PALETTE.accent,
        "axes.titlepad": 16,
        "axes.labelsize": 11,
        "axes.labelcolor": RV_PALETTE.fg,
        "axes.edgecolor": RV_PALETTE.border,
        "axes.facecolor": RV_PALETTE.bg,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.linewidth": 0.7,
        "axes.grid": True,
        "axes.axisbelow": True,
        "grid.color": RV_PALETTE.border_soft,
        "grid.alpha": 0.55,
        "grid.linewidth": 0.6,
        "xtick.color": RV_PALETTE.muted,
        "ytick.color": RV_PALETTE.muted,
        "xtick.labelsize": 10,
        "ytick.labelsize": 10,
        "legend.frameon": False,
        "legend.fontsize": 10.5,
    })


def style_axes(ax) -> None:
    ax.tick_params(length=0)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(RV_PALETTE.border)
