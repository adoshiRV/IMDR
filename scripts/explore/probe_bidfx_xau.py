"""Quick probe: does BidFX Historical Tick API return data for XAU/USD (gold)?

Tests multiple URL patterns and deal types to see what works.
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone

import requests

# -- bootstrap project settings --
sys.path.insert(0, ".")
from imdr.config.settings import get_settings

settings = get_settings()

session = requests.Session()
session.auth = (settings.bidfx_username, settings.bidfx_password)

# Last full hour window
now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
start = now - timedelta(hours=2)
end = now - timedelta(hours=1)
start_str = start.strftime("%Y%m%d%H%M%S")
end_str = end.strftime("%Y%m%d%H%M%S")

print(f"Window: {start} -> {end}")
print(f"Base URL: {settings.bidfx_base_url}")
print()

# Variations to try
base_urls = [
    settings.bidfx_base_url,                                    # .../v1/fx
    settings.bidfx_base_url.replace("/fx", "/commodities"),     # .../v1/commodities
    settings.bidfx_base_url.replace("/fx", "/metal"),           # .../v1/metal
    settings.bidfx_base_url.replace("/fx", "/precious_metals"), # .../v1/precious_metals
    settings.bidfx_base_url.replace("/v1/fx", "/v1"),           # .../v1  (no asset suffix)
]

pairs = ["XAU.USD", "XAUUSD"]
deal_types = ["Spot", "SPOT", "NDF", "Forward"]
tenors = ["SPOT", "Spot", "SP"]

# De-dup combos
tested = set()

for url in base_urls:
    for pair in pairs:
        for dt in deal_types:
            for tenor in tenors:
                key = (url, pair, dt, tenor)
                if key in tested:
                    continue
                tested.add(key)

                params = {
                    "currency_pair": pair,
                    "deal_type": dt,
                    "tenor": tenor,
                    "currency": "XAU",
                    "quantity": "1",
                    "start_time": start_str,
                    "end_time": end_str,
                }

                try:
                    resp = session.get(url, params=params, timeout=(5, 10))
                    status = resp.status_code
                    length = len(resp.content)
                    # Try to peek at response
                    try:
                        body = resp.json()
                        has_data = bool(body.get("data")) if isinstance(body, dict) else bool(body)
                    except Exception:
                        body = resp.text[:200]
                        has_data = False

                    marker = "** HAS DATA **" if has_data else ""
                    print(f"[{status}] {url}  pair={pair} deal_type={dt} tenor={tenor}  len={length}  {marker}")
                    if has_data or (status == 200 and length > 50):
                        print(f"  -> {str(body)[:300]}")
                        print()
                except Exception as exc:
                    print(f"[ERR] {url}  pair={pair} deal_type={dt} tenor={tenor}  -> {exc}")

print("\nDone.")
