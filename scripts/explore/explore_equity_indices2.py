"""Probe the EQUITY.EQUITY_INDEX..{TICKER} namespace more broadly.

We know the double-dot pattern works for data fetching even though
tagbrowsing can't navigate it. This script tries a broad set of
known index tickers and qualifiers to map the available universe.

Run:
    python -m scripts.explore.explore_equity_indices2

Output: data/cache/equity/equity_indices_universe.json
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from imdr.config.settings import get_settings
from imdr.connectors.citi_velocity import CitiVelocityClient

OUTPUT = Path("data/cache/equity/equity_indices_universe.json")
SLEEP = 1.1


def _summarize(series: dict | list) -> dict:
    if isinstance(series, dict) and "x" in series:
        xs, cs = series["x"], series["c"]
        return {"rows": len(xs),
                "first": xs[0] if xs else None, "last": xs[-1] if xs else None,
                "val_first": cs[0] if cs else None, "val_last": cs[-1] if cs else None}
    return {"rows": 0}


def batch_probe(client, tags, start, end, label=""):
    """Fetch historical for a batch, return {tag: summary}."""
    time.sleep(SLEEP)
    resp = client.fetch_historical(tags, start, end)
    results = {}
    if resp.get("status") == "OK":
        body = resp.get("body", {})
        for tag, series in body.items():
            s = _summarize(series)
            results[tag] = s
            if s["rows"] > 0:
                print(f"    {tag}: {s['rows']} pts [{s['val_first']}..{s['val_last']}]")
    else:
        print(f"    [{label}] ERROR: {resp.get('message')}")
    return results


def main() -> None:
    settings = get_settings()
    results: dict = {}

    end = datetime.now(timezone.utc)
    start_30d = end - timedelta(days=30)

    # Major global index tickers (BBG-style)
    INDEX_TICKERS = [
        # US
        "SPX", "NDX", "INDU", "RTY", "RUT", "VIX", "OEX", "MID", "CCMP",
        # Europe
        "FTSE", "UKX", "DAX", "SX5E", "SXXP", "CAC", "FCHI", "IBEX",
        "SMI", "AEX", "FTMIB", "OMX", "OMXS30", "BEL20", "PSI20",
        # Asia-Pacific
        "NKY", "N225", "TPX", "TOPX", "HSI", "HSCEI", "SHCOMP", "CSI300",
        "AS51", "AXJO", "KOSPI", "KS200", "TWSE", "NIFTY", "NSEI",
        "STI", "KLCI", "JCI", "SET", "PCOMP",
        # EM / Other
        "IBOV", "BVSP", "MEXBOL", "MERVAL", "COLCAP",
        "JALSH", "JTOPI", "MOEX", "WIG20", "XU030", "EGX30",
    ]

    ETF_TICKERS = [
        "SPY", "QQQ", "IWM", "DIA", "EEM", "EFA", "VWO", "GLD", "SLV",
        "TLT", "HYG", "LQD", "XLF", "XLK", "XLE", "XLV", "XLI", "XLY",
        "FXI", "EWJ", "EWZ", "EWG", "EWU",
    ]

    QUALIFIERS = ["LEVEL", "RETURN", "CLOSE", "OPEN", "HIGH", "LOW", "VOLUME"]
    SOURCES = ["REUTERS", "CITI"]

    with CitiVelocityClient(settings) as client:
        # ================================================================
        # PART 1: Probe indices with LEVEL.REUTERS (known working pattern)
        # ================================================================
        print("=" * 70)
        print("PART 1: INDEX TICKERS — EQUITY.EQUITY_INDEX..{TICKER}.LEVEL.REUTERS")
        print("=" * 70)

        # Batch in groups of 20 to avoid per-request limits
        idx_tags = [f"EQUITY.EQUITY_INDEX..{t}.LEVEL.REUTERS" for t in INDEX_TICKERS]
        idx_results = {}
        for i in range(0, len(idx_tags), 20):
            batch = idx_tags[i:i+20]
            print(f"\n  Batch {i//20 + 1} ({len(batch)} tags):")
            r = batch_probe(client, batch, start_30d, end, "IDX")
            idx_results.update(r)

        working_indices = [t for t, s in idx_results.items() if s["rows"] > 0]
        print(f"\n  Working: {len(working_indices)}/{len(idx_tags)}")
        results["indices_level_reuters"] = idx_results

        # ================================================================
        # PART 2: Probe ETFs
        # ================================================================
        print(f"\n{'=' * 70}")
        print("PART 2: ETF TICKERS")
        print("=" * 70)

        # Try both EQUITY_INDEX and EQUITY_ETF patterns
        etf_patterns = {}
        for pattern_name, template in [
            ("EQUITY_INDEX_dd", "EQUITY.EQUITY_INDEX..{}.LEVEL.REUTERS"),
            ("EQUITY_ETF_dd", "EQUITY.EQUITY_ETF..{}.LEVEL.REUTERS"),
        ]:
            tags = [template.format(t) for t in ETF_TICKERS]
            print(f"\n  Pattern: {pattern_name}")
            r = batch_probe(client, tags[:20], start_30d, end, pattern_name)
            etf_patterns[pattern_name] = r
            working = sum(1 for s in r.values() if s["rows"] > 0)
            print(f"  Working: {working}/{len(tags[:20])}")

        results["etf_probes"] = etf_patterns

        # ================================================================
        # PART 3: Probe qualifiers for SPX (what data types are available?)
        # ================================================================
        print(f"\n{'=' * 70}")
        print("PART 3: QUALIFIER PROBES FOR SPX")
        print("=" * 70)

        qual_tags = []
        for qual in QUALIFIERS:
            for src in SOURCES:
                qual_tags.append(f"EQUITY.EQUITY_INDEX..SPX.{qual}.{src}")

        print(f"\n  Trying {len(qual_tags)} qualifier combos for SPX:")
        qual_results = batch_probe(client, qual_tags, start_30d, end, "QUAL")
        results["spx_qualifiers"] = qual_results

        # ================================================================
        # PART 4: Try the same for a working index (NDX) to confirm
        # ================================================================
        print(f"\n{'=' * 70}")
        print("PART 4: QUALIFIER PROBES FOR NDX + FTSE")
        print("=" * 70)

        for idx in ["NDX", "FTSE"]:
            qtags = [f"EQUITY.EQUITY_INDEX..{idx}.{q}.{s}"
                     for q in QUALIFIERS for s in SOURCES]
            print(f"\n  {idx} ({len(qtags)} combos):")
            r = batch_probe(client, qtags, start_30d, end, idx)
            results[f"{idx}_qualifiers"] = r

        # ================================================================
        # PART 5: Try metadata on working tags
        # ================================================================
        print(f"\n{'=' * 70}")
        print("PART 5: METADATA ON WORKING TAGS")
        print("=" * 70)

        meta_tags = working_indices[:20]
        if meta_tags:
            time.sleep(SLEEP)
            meta = client.fetch_metadata(meta_tags)
            if meta.get("status") == "OK":
                for tag, info in meta.get("body", {}).items():
                    print(f"    {tag}: {info}")
            results["_metadata"] = meta

        # ================================================================
        # SUMMARY
        # ================================================================
        print(f"\n{'=' * 70}")
        print("SUMMARY")
        print(f"{'=' * 70}")

        idx_working = [t.split("..")[1].split(".")[0]
                       for t, s in idx_results.items() if s["rows"] > 0]
        print(f"\nWorking index tickers ({len(idx_working)}): {sorted(idx_working)}")

        for pname, data in etf_patterns.items():
            etf_working = [t for t, s in data.items() if s["rows"] > 0]
            print(f"\n{pname} working: {len(etf_working)}")
            if etf_working:
                print(f"  {etf_working[:10]}")

        spx_working = [t for t, s in qual_results.items() if s["rows"] > 0]
        print(f"\nSPX qualifier combos working ({len(spx_working)}):")
        for t in sorted(spx_working):
            print(f"  {t}")

        print(f"\nRate limit remaining: {client.rate_limit_remaining}")

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(results, indent=2, default=str))
    print(f"\nSaved to {OUTPUT}")


if __name__ == "__main__":
    main()
