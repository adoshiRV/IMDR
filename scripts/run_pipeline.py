"""Generic pipeline runner.

Usage:
    python -m scripts.run_pipeline fx.spot_rates --source csv --path data/fx.csv
    python -m scripts.run_pipeline fx.spot_rates --source bidfx
    python -m scripts.run_pipeline fx.ohlc --hour 2026-03-09T13:00:00
    python -m scripts.run_pipeline rates.historical --start 2024-01-01 --end 2024-01-31 --quotes par,spread
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from imdr.config.settings import get_settings
from imdr.connectors.mssql import MSSQLConnector
from imdr.pipelines.base import BasePipeline
from imdr.utils.logging import configure_logging

# Type alias for pipeline factory functions
PipelineFactory = Callable[[MSSQLConnector, argparse.Namespace], BasePipeline[Any, Any, Any]]


def _build_fx_pipeline(
    connector: MSSQLConnector, args: argparse.Namespace
) -> BasePipeline[Any, Any, Any]:
    """Build an FX pipeline based on CLI args."""
    from imdr.domains.fx.pipeline import FXSpotRatePipeline

    settings = get_settings()

    if args.source == "csv":
        if not args.path:
            print("ERROR: --path is required when source=csv")
            sys.exit(1)
        return FXSpotRatePipeline(connector, source_path=Path(args.path))

    if args.source in ("bidfx", "citivelocity"):
        from imdr.connectors.http import HTTPClient
        from imdr.domains.fx.extractors import BidFXExtractor, CitiVelocityExtractor

        api_key = settings.bidfx_api_key if args.source == "bidfx" else settings.citivelocity_api_key
        http = HTTPClient(
            timeout=settings.http_timeout,
            headers={"Authorization": f"Bearer {api_key}"} if api_key else {},
        )
        extractor = BidFXExtractor(http) if args.source == "bidfx" else CitiVelocityExtractor(http)
        return FXSpotRatePipeline(connector, extractor=extractor)

    print(f"ERROR: Unknown source '{args.source}'")
    sys.exit(1)


def _build_fx_ohlc_pipeline(
    connector: MSSQLConnector, args: argparse.Namespace
) -> BasePipeline[Any, Any, Any]:
    """Build an FX OHLC pipeline based on CLI args."""
    from datetime import datetime, timezone

    from imdr.domains.fx.pipeline_ohlc import FXOHLCPipeline
    from imdr.domains.fx.time_utils import HourWindow, last_full_utc_hour
    from imdr.universe.fx import get_fx_universe

    settings = get_settings()
    universe = get_fx_universe()

    if hasattr(args, "hour") and args.hour:
        start = datetime.fromisoformat(args.hour).replace(tzinfo=timezone.utc)
        from datetime import timedelta

        window = HourWindow(start=start, end=start + timedelta(hours=1))
    else:
        window = last_full_utc_hour()

    return FXOHLCPipeline(
        connector=connector,
        settings=settings,
        universe=universe,
        window=window,
    )


def _build_rates_historical_pipeline(
    connector: MSSQLConnector, args: argparse.Namespace
) -> BasePipeline[Any, Any, Any]:
    """Build a Rates Historical pipeline based on CLI args."""
    from datetime import datetime, timezone

    from imdr.domains.rates.pipeline import RatesHistoricalPipeline
    from imdr.universe.rates import get_rates_universe

    settings = get_settings()
    universe = get_rates_universe()

    if not hasattr(args, "start") or not args.start:
        print("ERROR: --start is required for rates.historical")
        sys.exit(1)
    if not hasattr(args, "end") or not args.end:
        print("ERROR: --end is required for rates.historical")
        sys.exit(1)

    start = datetime.strptime(args.start, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    end = datetime.strptime(args.end, "%Y-%m-%d").replace(
        hour=23, minute=59, tzinfo=timezone.utc
    )

    quotes = args.quotes.split(",") if hasattr(args, "quotes") and args.quotes else None

    return RatesHistoricalPipeline(
        connector=connector,
        settings=settings,
        universe=universe,
        start=start,
        end=end,
        quotes=quotes,
        frequency=getattr(args, "frequency", "DAILY") or "DAILY",
    )


def _build_fx_vol_pipeline(
    connector: MSSQLConnector, args: argparse.Namespace
) -> BasePipeline[Any, Any, Any]:
    """Build an FX Vol pipeline based on CLI args."""
    from datetime import datetime, timezone

    from imdr.domains.fx.pipeline_vol import FXVolPipeline
    from imdr.universe.fx import get_fx_universe

    settings = get_settings()
    universe = get_fx_universe()

    if not hasattr(args, "start") or not args.start:
        print("ERROR: --start is required for fx.vol")
        sys.exit(1)
    if not hasattr(args, "end") or not args.end:
        print("ERROR: --end is required for fx.vol")
        sys.exit(1)

    start = datetime.strptime(args.start, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    end = datetime.strptime(args.end, "%Y-%m-%d").replace(
        hour=23, minute=59, tzinfo=timezone.utc
    )

    # Optional --pairs flag: "EUR/USD,GBP/USD" → [("EUR","USD"), ("GBP","USD")]
    pairs = None
    if hasattr(args, "pairs") and args.pairs:
        pairs = [tuple(p.strip().split("/")) for p in args.pairs.split(",")]

    return FXVolPipeline(
        connector=connector,
        settings=settings,
        universe=universe,
        start=start,
        end=end,
        pairs=pairs,
    )


def _build_rates_vol_pipeline(
    connector: MSSQLConnector, args: argparse.Namespace
) -> BasePipeline[Any, Any, Any]:
    """Build a Rates Swaption Vol pipeline based on CLI args."""
    from datetime import datetime, timezone

    from imdr.domains.rates.pipeline_vol import RatesVolPipeline
    from imdr.universe.rates import get_rates_universe

    settings = get_settings()
    universe = get_rates_universe()

    if not hasattr(args, "start") or not args.start:
        print("ERROR: --start is required for rates.vol")
        sys.exit(1)
    if not hasattr(args, "end") or not args.end:
        print("ERROR: --end is required for rates.vol")
        sys.exit(1)

    start = datetime.strptime(args.start, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    end = datetime.strptime(args.end, "%Y-%m-%d").replace(
        hour=23, minute=59, tzinfo=timezone.utc
    )

    currencies = None
    if hasattr(args, "currencies") and args.currencies:
        currencies = [c.strip().upper() for c in args.currencies.split(",")]

    return RatesVolPipeline(
        connector=connector,
        settings=settings,
        universe=universe,
        start=start,
        end=end,
        currencies=currencies,
    )


def _build_cmdty_spot_pipeline(
    connector: MSSQLConnector, args: argparse.Namespace
) -> BasePipeline[Any, Any, Any]:
    """Build a Commodities SPOT pipeline based on CLI args."""
    from datetime import datetime, timezone

    from imdr.domains.commodities.pipeline_spot import CmdtySpotPipeline
    from imdr.universe.commodities import get_commodities_universe

    settings = get_settings()
    universe = get_commodities_universe()

    if not hasattr(args, "start") or not args.start:
        print("ERROR: --start is required for commodities.spot")
        sys.exit(1)
    if not hasattr(args, "end") or not args.end:
        print("ERROR: --end is required for commodities.spot")
        sys.exit(1)

    start = datetime.strptime(args.start, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    end = datetime.strptime(args.end, "%Y-%m-%d").replace(
        hour=23, minute=59, tzinfo=timezone.utc
    )

    return CmdtySpotPipeline(
        connector=connector, settings=settings,
        universe=universe, start=start, end=end,
    )


def _build_cmdty_eia_pipeline(
    connector: MSSQLConnector, args: argparse.Namespace
) -> BasePipeline[Any, Any, Any]:
    """Build a Commodities EIA pipeline based on CLI args."""
    from datetime import datetime, timezone

    from imdr.domains.commodities.pipeline_eia import CmdtyEIAPipeline
    from imdr.universe.commodities import get_commodities_universe

    settings = get_settings()
    universe = get_commodities_universe()

    if not hasattr(args, "start") or not args.start:
        print("ERROR: --start is required for commodities.eia")
        sys.exit(1)
    if not hasattr(args, "end") or not args.end:
        print("ERROR: --end is required for commodities.eia")
        sys.exit(1)

    start = datetime.strptime(args.start, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    end = datetime.strptime(args.end, "%Y-%m-%d").replace(
        hour=23, minute=59, tzinfo=timezone.utc
    )

    return CmdtyEIAPipeline(
        connector=connector, settings=settings,
        universe=universe, start=start, end=end,
    )


def _build_cmdty_vol_pipeline(
    connector: MSSQLConnector, args: argparse.Namespace
) -> BasePipeline[Any, Any, Any]:
    """Build a Commodities Implied Vol pipeline based on CLI args."""
    from datetime import datetime, timezone

    from imdr.domains.commodities.pipeline_vol import CmdtyImpliedVolPipeline
    from imdr.universe.commodities import get_commodities_universe

    settings = get_settings()
    universe = get_commodities_universe()

    if not hasattr(args, "start") or not args.start:
        print("ERROR: --start is required for commodities.vol")
        sys.exit(1)
    if not hasattr(args, "end") or not args.end:
        print("ERROR: --end is required for commodities.vol")
        sys.exit(1)

    start = datetime.strptime(args.start, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    end = datetime.strptime(args.end, "%Y-%m-%d").replace(
        hour=23, minute=59, tzinfo=timezone.utc
    )

    products = None
    if hasattr(args, "products") and args.products:
        products = [p.strip().upper() for p in args.products.split(",")]

    return CmdtyImpliedVolPipeline(
        connector=connector, settings=settings,
        universe=universe, start=start, end=end,
        products=products,
    )


def _build_equity_index_pipeline(
    connector: MSSQLConnector, args: argparse.Namespace
) -> BasePipeline[Any, Any, Any]:
    """Build an Equity Index pipeline based on CLI args."""
    from datetime import datetime, timezone

    from imdr.domains.equity.pipeline_index import EquityIndexPipeline
    from imdr.universe.equity import get_equity_universe

    settings = get_settings()
    universe = get_equity_universe()

    if not hasattr(args, "start") or not args.start:
        print("ERROR: --start is required for equity.index")
        sys.exit(1)
    if not hasattr(args, "end") or not args.end:
        print("ERROR: --end is required for equity.index")
        sys.exit(1)

    start = datetime.strptime(args.start, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    end = datetime.strptime(args.end, "%Y-%m-%d").replace(
        hour=23, minute=59, tzinfo=timezone.utc
    )
    return EquityIndexPipeline(
        connector=connector, settings=settings,
        universe=universe, start=start, end=end,
    )


def _build_equity_vix_pipeline(
    connector: MSSQLConnector, args: argparse.Namespace
) -> BasePipeline[Any, Any, Any]:
    """Build an Equity VIX pipeline based on CLI args."""
    from datetime import datetime, timezone

    from imdr.domains.equity.pipeline_vix import EquityVixPipeline
    from imdr.universe.equity import get_equity_universe

    settings = get_settings()
    universe = get_equity_universe()

    if not hasattr(args, "start") or not args.start:
        print("ERROR: --start is required for equity.vix")
        sys.exit(1)
    if not hasattr(args, "end") or not args.end:
        print("ERROR: --end is required for equity.vix")
        sys.exit(1)

    start = datetime.strptime(args.start, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    end = datetime.strptime(args.end, "%Y-%m-%d").replace(
        hour=23, minute=59, tzinfo=timezone.utc
    )
    return EquityVixPipeline(
        connector=connector, settings=settings,
        universe=universe, start=start, end=end,
    )


# Registry maps pipeline names to their factory functions.
# Add new pipelines here — no if-chain needed in main().
def _build_rates_skew_pipeline(
    connector: MSSQLConnector, args: argparse.Namespace
) -> BasePipeline[Any, Any, Any]:
    """Build a Rates Swaption Skew pipeline based on CLI args."""
    from datetime import datetime

    from imdr.domains.rates.pipeline_skew import RatesSkewPipeline

    settings = get_settings()

    # Resolve files
    if hasattr(args, "files") and args.files:
        file_paths = [Path(f) for f in args.files]
    else:
        skew_dir = Path(getattr(args, "skew_dir", "data/skew"))
        file_paths = sorted(skew_dir.glob("*.xlsx"))
        file_paths = [f for f in file_paths if not f.name.startswith("~$")]

    if not file_paths:
        print("ERROR: No .xlsx files found. Use --files or place files in data/skew/")
        sys.exit(1)

    start = datetime.strptime(args.start, "%Y-%m-%d").date() if args.start else None
    end = datetime.strptime(args.end, "%Y-%m-%d").date() if args.end else None

    # Resolve vendor_id
    from sqlalchemy import text
    with connector.session() as session:
        vendor_id = session.execute(
            text("SELECT id FROM [dbo].[dim_vendor] WHERE vendor_code = 'barclays'")
        ).scalar_one()

    return RatesSkewPipeline(
        connector=connector,
        settings=settings,
        file_paths=file_paths,
        vendor_id=vendor_id,
        start=start,
        end=end,
        chunk_size=settings.bulk_batch_size,
    )


def _build_rates_bench_pipeline(
    connector: MSSQLConnector, args: argparse.Namespace
) -> BasePipeline[Any, Any, Any]:
    """Build a Rates Bench Rates pipeline based on CLI args."""
    from datetime import datetime, timezone

    from imdr.domains.rates.pipeline_bench import BenchRatesPipeline
    from imdr.universe.rates import get_rates_universe

    settings = get_settings()
    universe = get_rates_universe()

    if not hasattr(args, "start") or not args.start:
        print("ERROR: --start is required for rates.bench_rates")
        sys.exit(1)
    if not hasattr(args, "end") or not args.end:
        print("ERROR: --end is required for rates.bench_rates")
        sys.exit(1)

    start = datetime.strptime(args.start, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    end = datetime.strptime(args.end, "%Y-%m-%d").replace(
        hour=23, minute=59, tzinfo=timezone.utc
    )

    return BenchRatesPipeline(
        connector=connector, settings=settings,
        universe=universe, start=start, end=end,
    )


def _build_fx_rate_pipeline(
    connector: MSSQLConnector, args: argparse.Namespace
) -> BasePipeline[Any, Any, Any]:
    """Build an FX Citi rate pipeline based on CLI args."""
    from datetime import datetime, timezone

    from imdr.domains.fx.pipeline_rate import FXRatePipeline
    from imdr.universe.fx import get_fx_universe

    settings = get_settings()
    universe = get_fx_universe()

    if not hasattr(args, "start") or not args.start:
        print("ERROR: --start is required for fx.citi_rate")
        sys.exit(1)
    if not hasattr(args, "end") or not args.end:
        print("ERROR: --end is required for fx.citi_rate")
        sys.exit(1)

    start = datetime.strptime(args.start, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    end = datetime.strptime(args.end, "%Y-%m-%d").replace(
        hour=23, minute=59, tzinfo=timezone.utc
    )

    pairs = None
    if hasattr(args, "pairs") and args.pairs:
        pairs = [tuple(p.strip().split("/")) for p in args.pairs.split(",")]

    return FXRatePipeline(
        connector=connector,
        settings=settings,
        universe=universe,
        start=start,
        end=end,
        pairs=pairs,
        chunk_size=settings.bulk_batch_size,
    )


PIPELINE_REGISTRY: dict[str, PipelineFactory] = {
    "fx.spot_rates": _build_fx_pipeline,
    "fx.ohlc": _build_fx_ohlc_pipeline,
    "fx.vol": _build_fx_vol_pipeline,
    "fx.citi_rate": _build_fx_rate_pipeline,
    "rates.historical": _build_rates_historical_pipeline,
    "rates.vol": _build_rates_vol_pipeline,
    "rates.skew": _build_rates_skew_pipeline,
    "rates.bench_rates": _build_rates_bench_pipeline,
    "commodities.spot": _build_cmdty_spot_pipeline,
    "commodities.eia": _build_cmdty_eia_pipeline,
    "commodities.vol": _build_cmdty_vol_pipeline,
    "equity.index": _build_equity_index_pipeline,
    "equity.vix": _build_equity_vix_pipeline,
}


def main() -> int:
    parser = argparse.ArgumentParser(description="IMDR Pipeline Runner")
    parser.add_argument("pipeline", choices=PIPELINE_REGISTRY.keys(), help="Pipeline to run")
    parser.add_argument("--source", default="csv", help="Data source (csv, bidfx, citivelocity)")
    parser.add_argument("--path", type=str, help="File path (when source=csv)")
    parser.add_argument("--hour", type=str, help="Hour override for fx.ohlc (ISO format)")
    parser.add_argument("--start", type=str, help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", type=str, help="End date (YYYY-MM-DD)")
    parser.add_argument("--quotes", type=str, help="Comma-separated quote types for rates.historical (par,spread,fwd)")
    parser.add_argument("--pairs", type=str, help="Comma-separated pairs for fx.vol (EUR/USD,GBP/USD)")
    parser.add_argument("--frequency", type=str, help="Data frequency (DAILY, HOURLY)")
    parser.add_argument("--currencies", type=str, help="Comma-separated currencies for rates.vol (USD,EUR,JPY)")
    parser.add_argument("--products", type=str, help="Comma-separated products for commodities.vol (XAU,XAG)")
    parser.add_argument("--files", nargs="+", type=str, help="Excel file paths for rates.skew")
    parser.add_argument("--skew-dir", type=str, default="data/skew", dest="skew_dir", help="Directory for rates.skew Excel files")
    args = parser.parse_args()

    settings = get_settings()
    configure_logging(settings)
    connector = MSSQLConnector(settings)

    try:
        factory = PIPELINE_REGISTRY[args.pipeline]
        pipeline = factory(connector, args)
        result = pipeline.run()
        print(f"Pipeline '{args.pipeline}' completed. Rows loaded: {result}")
        return 0
    except Exception as exc:
        print(f"Pipeline '{args.pipeline}' FAILED: {exc}")
        return 1
    finally:
        connector.dispose()


if __name__ == "__main__":
    sys.exit(main())
