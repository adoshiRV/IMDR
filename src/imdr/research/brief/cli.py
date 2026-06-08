"""Operator CLI for the macro brief pipeline.

Usage::

    python -m imdr.research.brief weekly --config <path/to/weekly.yml>
    python -m imdr.research.brief daily  --config <path/to/daily.yml>
    python -m imdr.research.brief validate --config <path>     # parse-only

``--date`` is read from the YAML (``period_date``). Pass ``--out-dir`` to
override the default output location (rarely needed; default keeps the
date-sharded layout under ``data/research_summaries/``).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .config import load_config
from .pipeline import build_daily, build_weekly


def _cmd_weekly(args: argparse.Namespace) -> int:
    res = build_weekly(args.config)
    _print_result(res)
    return 0 if res.audit["checks"]["html_written"] else 1


def _cmd_daily(args: argparse.Namespace) -> int:
    res = build_daily(args.config)
    _print_result(res)
    return 0 if res.audit["checks"]["html_written"] else 1


def _cmd_validate(args: argparse.Namespace) -> int:
    cfg = load_config(args.config)
    print(f"OK  {args.config}")
    print(f"    type        : {cfg.brief_type}")
    print(f"    period_date : {cfg.period_date}")
    return 0


def _print_result(res) -> None:
    print(f"HTML  : {res.out_html}")
    print(f"charts: {len(res.charts)}  PDFs: {len(res.pdf_pages)}  links: {res.report_link_count}")
    a = res.audit
    print(f"audit : SP hrefs={a['sharepoint_href_count']}  HTML size={a['html_kb']} KB  checks={a['checks']}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="python -m imdr.research.brief",
        description="Generate RV-styled weekly/daily macro briefs.",
    )
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_weekly = sub.add_parser("weekly", help="Build a weekly preview")
    p_weekly.add_argument("--config", type=Path, required=True)
    p_weekly.set_defaults(func=_cmd_weekly)

    p_daily = sub.add_parser("daily", help="Build a daily brief")
    p_daily.add_argument("--config", type=Path, required=True)
    p_daily.set_defaults(func=_cmd_daily)

    p_val = sub.add_parser("validate", help="Parse-check a config")
    p_val.add_argument("--config", type=Path, required=True)
    p_val.set_defaults(func=_cmd_validate)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
