"""Citi Velocity FX proprietary-index ingest -> fx.dim_index_series + fx.fact_index_value.

Ingests the Citi FX proprietary-index group (Surprise Index / CESI, NEER, REER,
CTOT, MRI, Pain, CRFI, Liquidity) from the Velocity `FX.<PRODUCT>` tag roots into
the generic index framework. Library logic lives in
`src/imdr/domains/fx/citi_fx_indices.py`; this is the batched fetch/load
entrypoint with the standard RunReport plumbing.

    # dry run — fetch + report, write nothing (default, safe):
    python -m scripts.fx.citi.fx_indices --no-load

    # one product only:
    python -m scripts.fx.citi.fx_indices --product NEER_IDX --no-load

    # full history backfill of all products (needs migrations 120-122 applied):
    python -m scripts.fx.citi.fx_indices --mode backfill --load

    # daily catch-up (last 10 calendar days):
    python -m scripts.fx.citi.fx_indices --mode daily --load

SC_SCORECARD is intentionally excluded (deferred Phase 2 — dataless tags).
"""

from __future__ import annotations

import argparse
import datetime
import sys
import time
from pathlib import Path

import structlog
from sqlalchemy import text

from imdr.config.settings import get_settings
from imdr.connectors.citi_helpers import (
    TagQuotaExceeded,
    iter_fetched_batches,
    summarize_tag_errors,
)
from imdr.connectors.citi_quota import TagQuotaTracker
from imdr.connectors.citi_velocity import CitiVelocityClient
from imdr.connectors.mssql import MSSQLConnector
from imdr.domains.fx import citi_fx_indices as cfi
from imdr.reporting.run_report import RunReport
from imdr.utils.logging import configure_logging

log = structlog.get_logger(__name__)

PIPELINE_NAME = "fx.citi_fx_indices"
BACKFILL_START = datetime.date(2005, 1, 1)
DAILY_LOOKBACK_DAYS = 10
# Products whose upstream history ends ~Oct 2025 (likely discontinued): a
# zero-obs daily run for these is EXPECTED, not a fetch break -- but still worth
# a scoped signal in case Citi reinstates them or the fetch actually broke.
STALE_PRODUCTS = frozenset({"CRFI", "LIQUIDITY_IDX"})


def _parse_obs_date(x: int | str) -> datetime.date | None:
    """Citi x-axis -> date. All supported products are daily (8-digit YYYYMMDD)."""
    s = str(x)
    if len(s) != 8:
        return None
    try:
        return datetime.datetime.strptime(s, "%Y%m%d").date()
    except ValueError:
        return None


def _fetch_currency_codes(connector: MSSQLConnector) -> set[str]:
    with connector.engine.connect() as conn:
        rows = conn.execute(text("SELECT code FROM dbo.dim_currency")).all()
    return {r[0].upper() for r in rows if r[0]}


def _list_tags(client: CitiVelocityClient, prefix: str) -> list[str]:
    resp = client.fetch_taglisting(prefix)
    if resp.get("status") != "OK":
        raise RuntimeError(f"taglisting failed for {prefix}: {resp.get('message', resp)}")
    return sorted(resp.get("tags", []))


def _resp_to_values(resp: dict) -> tuple[list[cfi.ValueRow], int]:
    """Parse one Citi Historical response into ValueRows. Returns (rows, n_bad)."""
    values: list[cfi.ValueRow] = []
    n_bad = 0
    for tag, series in resp.get("body", {}).items():
        if not isinstance(series, dict):
            continue
        xs = series.get("x") or []
        cs = series.get("c") or []
        for x, c in zip(xs, cs):
            if c is None:
                continue
            d = _parse_obs_date(x)
            if d is None:
                n_bad += 1
                continue
            values.append(cfi.ValueRow(citi_tag=tag, obs_date=d, value=float(c)))
    return values, n_bad


def _run_product(
    client: CitiVelocityClient,
    connector: MSSQLConnector,
    product: str,
    currency_codes: set[str],
    start_dt: datetime.datetime,
    end_dt: datetime.datetime,
    batch_size: int,
    rate_limit_sec: float,
    load: bool,
    limit: int,
    quota_tracker: TagQuotaTracker,
    tag_errors: list[dict],
) -> dict:
    """List + build + (upsert) + stream-fetch/load one product. Returns a summary dict.

    Fetch goes through the shared ``iter_fetched_batches`` (5xx retry, tag-quota
    recording, per-tag error capture, rate limiting); each batch is parsed and
    loaded immediately so a full-history backfill is never held in memory.
    """
    prefix = cfi.PRODUCT_PREFIXES[product]
    tags = _list_tags(client, prefix)
    if limit > 0:
        tags = tags[:limit]
    series = cfi.build_series(tags, currency_codes)
    n_with_ccy = sum(1 for s in series if s.region_currency_code)

    tag_to_id: dict[str, int] = {}
    if load:
        tag_to_id = cfi.upsert_series(connector, series)

    totals = {"staged": 0, "inserted_new": 0, "inserted_revision": 0,
              "skipped": 0, "duplicates_collapsed": 0}
    n_obs = n_bad = n_calls = 0
    sample: list[tuple[str, datetime.date, float]] = []  # first few (tag, date, val)

    for resp in iter_fetched_batches(
        client, tags, start_dt, end_dt, "DAILY", batch_size, rate_limit_sec,
        quota_tracker=quota_tracker, pipeline_name=PIPELINE_NAME, tag_errors=tag_errors,
    ):
        vals, bad = _resp_to_values(resp)
        n_calls += 1
        n_obs += len(vals)
        n_bad += bad
        if len(sample) < 4 and vals:
            latest = max(vals, key=lambda v: v.obs_date)
            sample.append((latest.citi_tag, latest.obs_date, latest.value))
        if load and vals:
            st = cfi.load_values(connector, vals, tag_to_id)
            for k in totals:
                totals[k] += st[k]

    log.info("product_done", product=product, n_series=len(tags), n_obs=n_obs, n_calls=n_calls)
    return {"product": product, "n_series": len(tags), "n_series_with_ccy": n_with_ccy,
            "n_obs": n_obs, "n_bad": n_bad, "n_calls": n_calls, "totals": totals,
            "sample": sample}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ingest Citi Velocity FX proprietary indices")
    parser.add_argument("--product", action="append",
                        help=f"product(s) to ingest (repeatable); default all. "
                             f"Choices: {', '.join(cfi.PRODUCT_PREFIXES)}")
    parser.add_argument("--mode", choices=["backfill", "daily"], default="daily")
    parser.add_argument("--start", help="YYYY-MM-DD (overrides mode default)")
    parser.add_argument("--end", help="YYYY-MM-DD (default today)")
    load_grp = parser.add_mutually_exclusive_group()
    load_grp.add_argument("--load", dest="load", action="store_true", help="write to the DB")
    load_grp.add_argument("--no-load", dest="load", action="store_false",
                          help="dry run: fetch + report only (default)")
    parser.set_defaults(load=False)
    parser.add_argument("--batch-size", type=int, default=50, help="tags per historical call (<=100)")
    parser.add_argument("--limit", type=int, default=0, help="cap tags per product (testing); 0 = all")
    args = parser.parse_args(argv)

    products = args.product or list(cfi.PRODUCT_PREFIXES)
    unknown = [p for p in products if p not in cfi.PRODUCT_PREFIXES]
    if unknown:
        parser.error(f"unknown product(s): {unknown}. Choices: {list(cfi.PRODUCT_PREFIXES)}")

    settings = get_settings()
    configure_logging(settings)

    today = datetime.date.today()
    end = datetime.date.fromisoformat(args.end) if args.end else today
    if args.start:
        start = datetime.date.fromisoformat(args.start)
    elif args.mode == "backfill":
        start = BACKFILL_START
    else:
        start = end - datetime.timedelta(days=DAILY_LOOKBACK_DAYS)
    start_dt = datetime.datetime(start.year, start.month, start.day, tzinfo=datetime.timezone.utc)
    end_dt = datetime.datetime(end.year, end.month, end.day, 23, 59, tzinfo=datetime.timezone.utc)

    batch_size = min(max(args.batch_size, 1), 100)
    report = RunReport(pipeline_name=PIPELINE_NAME)
    connector = MSSQLConnector(settings)
    quota_tracker = TagQuotaTracker(
        quota_limit=settings.citi_tag_quota_limit,
        tracker_path=settings.citi_tag_quota_file or None,
    )
    tag_errors: list[dict] = []
    log.info("ingest_start", products=products, mode=args.mode,
             start=str(start), end=str(end), load=args.load, batch_size=batch_size)

    try:
        t0 = time.perf_counter()
        currency_codes = _fetch_currency_codes(connector)
        results: list[dict] = []

        with CitiVelocityClient(settings) as client:
            for product in products:
                try:
                    res = _run_product(
                        client, connector, product, currency_codes,
                        start_dt, end_dt, batch_size, settings.citi_rate_limit_sec,
                        args.load, args.limit, quota_tracker, tag_errors,
                    )
                except TagQuotaExceeded as e:
                    # Quota is shared + exhausted -> no point trying more products.
                    log.error("tag_quota_exhausted", product=product, remaining=quota_tracker.remaining())
                    report.error("tag_quota", f"Tag quota exhausted at {product}; stopped ({e})")
                    break
                except Exception:
                    # Isolate a single product's hard failure so the rest still run.
                    log.exception("product_failed", product=product)
                    report.error("product", f"{product} failed — skipped")
                    continue
                results.append(res)
                report.info("product", f"{product}: {res['n_series']} series, {res['n_obs']:,} obs",
                            details={k: res[k] for k in ("n_series", "n_series_with_ccy", "n_obs",
                                                          "n_bad", "n_calls")})
                # Stale products legitimately return no fresh obs in daily mode;
                # signal (scoped) so a real fetch break isn't mistaken for staleness.
                if res["n_obs"] == 0 and product in STALE_PRODUCTS:
                    log.warning("product_zero_obs_stale", product=product)
                    report.warning("staleness",
                                   f"{product} returned 0 obs (known stale since Oct 2025 — "
                                   f"verify reinstatement / fetch not broken)")

        err_summary = summarize_tag_errors(tag_errors)
        if err_summary:
            report.info("tag_errors", f"{len(tag_errors)} tag issue(s) across products",
                        details={"top": err_summary[:5]})

        _print_report(results, start, end, load=args.load)

        if args.load:
            grand = {k: sum(r["totals"][k] for r in results)
                     for k in ("inserted_new", "inserted_revision", "skipped", "duplicates_collapsed")}
            report.info("fact", "vintage-aware load complete", details=grand)

        elapsed = time.perf_counter() - t0
        log.info("ingest_complete", elapsed=f"{elapsed:.1f}s",
                 n_products=len(results), n_obs=sum(r["n_obs"] for r in results))
        report.finish()
        _flush(report, settings)
        return 0

    except Exception:
        log.exception("ingest_failed")
        report.error("pipeline", "FX proprietary-index ingest failed")
        report.finish()
        _flush(report, settings)
        return 1
    finally:
        connector.dispose()


def _print_report(results: list[dict], start, end, load: bool) -> None:
    tag = "LOADED" if load else "DRY RUN"
    print(f"\n[{tag}] Citi FX proprietary indices ({start}..{end})")
    print(f"  {'product':<16}{'series':>8}{'ccy_fk':>8}{'obs':>12}  {'load (new/rev/skip)' if load else 'sample latest'}")
    for r in results:
        if load:
            t = r["totals"]
            detail = f"{t['inserted_new']:,}/{t['inserted_revision']:,}/{t['skipped']:,}"
        else:
            detail = ""
            if r["sample"]:
                tg, d, v = r["sample"][0]
                detail = f"{tg.split('.', 2)[-1]} = {v:g} ({d})"
        print(f"  {r['product']:<16}{r['n_series']:>8}{r['n_series_with_ccy']:>8}{r['n_obs']:>12,}  {detail}")
    print(f"  {'TOTAL':<16}{sum(r['n_series'] for r in results):>8}"
          f"{sum(r['n_series_with_ccy'] for r in results):>8}"
          f"{sum(r['n_obs'] for r in results):>12,}")


def _flush(report: RunReport, settings: object) -> None:
    if getattr(settings, "run_log_dir", ""):
        ts = datetime.datetime.now(datetime.timezone.utc)
        path = (Path(settings.run_log_dir) / "fx" / "fact_index_value"
                / f"citi_fx_indices_{ts:%Y%m%d_%H%M%S}.jsonl")
        report.flush_jsonl(path)


if __name__ == "__main__":
    sys.exit(main())
