"""Probe Citi BASIS_SWAPS — confirm data on the *unwired* bases.

The existing universe only wires `3S6S_BASIS` (EUR + AUD live). The
BASIS_SWAPS catalog also contains:

    - 3S_OIS_BASIS          (USD/EUR/GBP/AUD)  — classic IBOR-OIS funding stress
    - SOFR_FEDFUND_BASIS    (USD)              — US repo vs unsecured stress
    - EUROSTR_EURIBOR_BASIS (EUR)              — post-LIBOR EUR funding basis
    - SOFR_LIBOR_BASIS      (USD)              — likely dead post USD LIBOR cessation
    - 3S1S_BASIS            (USD/EUR/GBP/AUD)  — tenor microstructure

Tag listings exist (cached in basis_swaps_probe.json) but data was never
confirmed end-to-end. This probe fetches actual tag lists per (base, ccy),
pulls last-30-day samples for ~3 tenors, reports the latest observation
date + value, and writes a fresh cache so we can decide which bases are
worth wiring.

Run:
    python -m playground.rates.probe_basis_swaps_other_bases
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from imdr.config.settings import get_settings
from imdr.connectors.citi_velocity import CitiVelocityClient

CACHE_DIR = Path("data/cache/rates")
OUTPUT_PATH = CACHE_DIR / "basis_swaps_other_bases_probe.json"
SLEEP = 1.2
LOOKBACK_DAYS = 30

# (base, ccys) — derived from cached tag listings in basis_swaps_probe.json
TARGETS: list[tuple[str, list[str]]] = [
    ("3S_OIS_BASIS",          ["USD", "EUR", "GBP", "AUD"]),
    ("SOFR_FEDFUND_BASIS",    ["USD"]),
    ("EUROSTR_EURIBOR_BASIS", ["EUR"]),
    ("SOFR_LIBOR_BASIS",      ["USD"]),
    ("3S1S_BASIS",            ["USD", "EUR", "GBP", "AUD"]),
]


def _normalise_date(raw) -> str | None:
    """Citi returns dates as int epoch (ms or yyyymmdd) or str. Coerce → ISO date."""
    if raw is None:
        return None
    if isinstance(raw, int):
        # yyyymmdd integer (e.g. 20260605)
        if 19000101 <= raw <= 21001231:
            s = str(raw)
            return f"{s[0:4]}-{s[4:6]}-{s[6:8]}"
        # epoch seconds
        if 10**9 <= raw <= 2 * 10**10:
            return datetime.fromtimestamp(raw, tz=timezone.utc).date().isoformat()
        # epoch milliseconds
        if 10**12 <= raw <= 2 * 10**13:
            return datetime.fromtimestamp(raw / 1000, tz=timezone.utc).date().isoformat()
        return str(raw)
    if isinstance(raw, str):
        return raw[:10]
    return str(raw)


def _classify(latest_iso: str | None, now: datetime) -> str:
    if not latest_iso:
        return "no_data"
    try:
        d = datetime.strptime(latest_iso[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError:
        return "no_data"
    age_days = (now - d).days
    if age_days <= 7:
        return "live"
    if age_days <= 60:
        return "stale"
    return "dead"


def _pick_sample_tenors(tags: list[str]) -> list[str]:
    """Pick ~3 representative tenors from the actual tag list (prefer 1Y/5Y/10Y, else first 3)."""
    preferred = ["1Y", "5Y", "10Y"]
    picked: list[str] = []
    for t in tags:
        parts = t.split(".")
        if len(parts) < 7:
            continue
        if parts[5] in preferred:
            picked.append(t)
    if picked:
        return picked
    return tags[:3]


def main() -> None:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    start = now - timedelta(days=LOOKBACK_DAYS)

    results: dict = {"probed_at": now.isoformat(), "by_base": {}}

    with CitiVelocityClient(settings) as client:
        for base, ccys in TARGETS:
            print("=" * 60)
            print(f"{base}")
            print("=" * 60)
            results["by_base"][base] = {}

            for ccy in ccys:
                prefix = f"RATES.BASIS_SWAPS.{base}.{ccy}.SPOT."
                time.sleep(SLEEP)
                try:
                    listing = client.fetch_taglisting(prefix)
                    all_tags = listing.get("tags", []) or []
                except Exception as e:
                    print(f"  {ccy}: TAG LISTING ERROR {e}")
                    results["by_base"][base][ccy] = {"error": f"listing: {e}"}
                    continue

                if not all_tags:
                    print(f"  {ccy}: no tags listed")
                    results["by_base"][base][ccy] = {"status": "no_tags", "n_tags": 0}
                    continue

                sample = _pick_sample_tenors(all_tags)
                time.sleep(SLEEP)
                try:
                    resp = client.fetch_historical(sample, start, now)
                    body = resp.get("body", {})
                except Exception as e:
                    print(f"  {ccy}: DATA FETCH ERROR {e}")
                    results["by_base"][base][ccy] = {
                        "error": f"data: {e}",
                        "n_tags": len(all_tags),
                        "sample_tags": sample,
                    }
                    continue

                per_tag: dict[str, dict] = {}
                latest_overall: str | None = None
                for tag in sample:
                    td = body.get(tag, {}) or {}
                    raw_dates = td.get("x", []) or []
                    raw_vals = td.get("c", []) or []
                    iso_dates = [_normalise_date(d) for d in raw_dates]
                    if raw_vals and iso_dates:
                        per_tag[tag] = {
                            "n_obs": len(raw_vals),
                            "latest_date": iso_dates[-1],
                            "latest_value": raw_vals[-1],
                            "first_date": iso_dates[0],
                        }
                        if iso_dates[-1] and (latest_overall is None or iso_dates[-1] > latest_overall):
                            latest_overall = iso_dates[-1]
                    else:
                        per_tag[tag] = {"n_obs": 0}

                status = _classify(latest_overall, now)
                results["by_base"][base][ccy] = {
                    "status": status,
                    "n_tags": len(all_tags),
                    "sample_tags": sample,
                    "latest_date": latest_overall,
                    "per_tag": per_tag,
                }
                latest_disp = latest_overall or "n/a"
                live_tags = sum(1 for t in per_tag.values() if t.get("n_obs", 0) > 0)
                print(
                    f"  {ccy}: tags={len(all_tags):3d} status={status:7s} "
                    f"latest={latest_disp[:10]} sampled_with_data={live_tags}/{len(sample)}"
                )

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(results, indent=2, default=str))

    print()
    print("=" * 60)
    print("Verdict matrix")
    print("=" * 60)
    print(f"  {'BASE':25s} {'CCY':4s} {'STATUS':8s} {'TAGS':5s} {'LATEST':12s}")
    for base, by_ccy in results["by_base"].items():
        for ccy, info in by_ccy.items():
            ld = (info.get("latest_date") or "")[:10] or "n/a"
            st = info.get("status") or "error"
            nt = info.get("n_tags", 0)
            print(f"  {base:25s} {ccy:4s} {st:8s} {nt:>5d} {ld:12s}")
    print(f"\nSaved to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
