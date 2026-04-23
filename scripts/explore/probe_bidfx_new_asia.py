"""Probe BidFX for newly added Asia currencies (MYR, VND, HKD).

Extract-only — no DB write, no email. Prints bars produced and drop reasons
so we can confirm BidFX quotes these pairs before enabling them in the live
scheduler.

Usage:
    python -m scripts.explore.probe_bidfx_new_asia
"""

from __future__ import annotations

from imdr.config.settings import get_settings
from imdr.domains.fx.extractors import BidFXExtractor
from imdr.domains.fx.time_utils import last_full_utc_hour
from imdr.universe.fx import get_fx_universe
from imdr.utils.logging import configure_logging

TARGETS = {"MYR", "VND", "HKD"}


def main() -> int:
    settings = get_settings()
    configure_logging(settings)

    universe = get_fx_universe()
    window = last_full_utc_hour()

    print(f"Window: {window}")
    print(f"Probing currencies: {sorted(TARGETS)}")
    print(f"FX market open: {universe.is_fx_open(window.start)}")
    print()

    extractor = BidFXExtractor(
        settings=settings,
        universe=universe,
        window=window,
        pair_cache=None,
        currencies=TARGETS,
    )
    bars = extractor.extract()

    print(f"Bars produced: {len(bars)}")
    for b in bars:
        print(
            f"  {b.get('symbol'):8s} {b.get('series'):10s} "
            f"o={b.get('open_px')} h={b.get('high_px')} "
            f"l={b.get('low_px')} c={b.get('close_px')} "
            f"ticks={b.get('tick_count')} pair={b.get('pair_used')}"
        )

    drops = [d for d in extractor.diagnostics if not d.success]
    print(f"\nDrops: {len(drops)}")
    for d in drops:
        print(f"  {d.symbol:10s} {d.series:10s} reason={d.reason}")

    success = {d.symbol for d in extractor.diagnostics if d.success}
    produced_ccys = {b.get("symbol", "")[:3] if b.get("symbol", "").startswith("USD") else b.get("symbol", "")[-3:] for b in bars}
    confirmed = TARGETS & {c for c in [
        "MYR", "VND", "HKD",
    ] if any(c in b.get("symbol", "") or c in b.get("pair_used", "") for b in bars)}
    print(f"\nConfirmed quoted: {sorted(confirmed)}")
    print(f"No bars:          {sorted(TARGETS - confirmed)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
