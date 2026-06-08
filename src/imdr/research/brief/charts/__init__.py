"""Chart generation — RV-styled matplotlib charts written as PNG."""
from .base import RV_PALETTE, configure_matplotlib
from .builder import build_all_charts

__all__ = ["RV_PALETTE", "build_all_charts", "configure_matplotlib"]
