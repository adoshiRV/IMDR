"""Probe BidFX for all possible tenors on EURUSD (known good pair).

First validates connectivity with a known-good call, then tests all tenors.
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone

import requests

sys.path.insert(0, ".")
from imdr.config.settings import get_settings

settings = get_settings()

session = requests.Session()
session.auth = (settings.bidfx_username, settings.bidfx_password)

now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
start = now - timedelta(hours=2)
end = now - timedelta(hours=1)
start_str = start.strftime("%Y%m%d%H%M%S")
end_str = end.strftime("%Y%m%d%H%M%S")

print(f"Window: {start} -> {end}")
print(f"URL: {settings.bidfx_base_url}")
print()

PAIR = "EURUSD"
URL = settings.bidfx_base_url

# --- Sanity check: known good call (Spot) ---
print("=== Sanity check: EURUSD Spot ===")
params_check = {
    "currency_pair": PAIR,
    "deal_type": "Spot",
    "tenor": "Spot",
    "currency": "EUR",
    "quantity": "1000000",
    "start_time": start_str,
    "end_time": end_str,
}
resp = session.get(URL, params=params_check, timeout=(5, 15))
print(f"Status: {resp.status_code}, Length: {len(resp.content)}")
if resp.status_code == 200:
    try:
        body = resp.json()
        if isinstance(body, dict):
            n = len(body.get("data", []))
            print(f"Ticks: {n}")
            if n > 0:
                print(f"First tick keys: {list(body['data'][0].keys())}")
        else:
            print(f"Response type: {type(body)}, len={len(body) if hasattr(body, '__len__') else '?'}")
    except Exception:
        print(f"Body: {resp.text[:300]}")
else:
    print(f"Error: {resp.text[:300]}")
print()

# --- Probe all tenors ---
TENORS = [
    # Ultra-short
    "ON", "TN", "SN",
    # Weeks
    "1W", "2W", "3W",
    # Months
    "1M", "2M", "3M", "4M", "5M", "6M", "7M", "8M", "9M", "10M", "11M",
    # Years
    "1Y", "15M", "18M", "2Y", "3Y", "4Y", "5Y", "7Y", "10Y", "15Y", "20Y", "25Y", "30Y",
    # IMM
    "IMM1", "IMM2", "IMM3", "IMM4",
    # Today/Tom
    "TOD", "TOM",
    # Spot (for Forward deal_type)
    "Spot",
]

DEAL_TYPES = ["Spot", "Forward", "NDF", "Swap"]

print(f"{'DEAL_TYPE':<12} {'TENOR':<10} {'STATUS':>6} {'LEN':>6} {'TICKS':>6}  NOTE")
print("-" * 80)

hits = []

for deal_type in DEAL_TYPES:
    for tenor in TENORS:
        params = {
            "currency_pair": PAIR,
            "deal_type": deal_type,
            "tenor": tenor,
            "currency": "EUR",
            "quantity": "1000000",
            "start_time": start_str,
            "end_time": end_str,
        }

        try:
            resp = session.get(URL, params=params, timeout=(5, 10))
            status = resp.status_code
            length = len(resp.content)

            n_ticks = 0
            note = ""
            if status == 200:
                try:
                    body = resp.json()
                    if isinstance(body, dict):
                        data = body.get("data", [])
                        n_ticks = len(data) if isinstance(data, list) else 0
                        if n_ticks > 0:
                            sample = data[0]
                            note = f"keys={list(sample.keys())[:6]}"
                    elif isinstance(body, list):
                        n_ticks = len(body)
                except Exception:
                    note = resp.text[:60]

            if n_ticks > 0:
                hits.append((deal_type, tenor, n_ticks))
                print(f"{deal_type:<12} {tenor:<10} {status:>6} {length:>6} {n_ticks:>6}  ** DATA **  {note}")
            elif status == 200:
                print(f"{deal_type:<12} {tenor:<10} {status:>6} {length:>6} {n_ticks:>6}  (empty 200)")
            elif status not in (400, 404):
                print(f"{deal_type:<12} {tenor:<10} {status:>6} {length:>6}         {resp.text[:80]}")

        except Exception as exc:
            print(f"{deal_type:<12} {tenor:<10}    ERR              {exc}")

print()
print("=" * 80)
print("SUMMARY — Tenors with data:")
print("=" * 80)
if hits:
    for deal_type, tenor, n in hits:
        print(f"  {deal_type:<12} {tenor:<10} {n:>6} ticks")
else:
    print("  No data returned for any tenor combination.")

print("\nDone.")
