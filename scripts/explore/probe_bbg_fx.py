"""Probe BBG FX CSV files — runs the user's FXFWDs loop and shows head of each."""
import datetime as dt
import os

import pandas as pd

pd.set_option("display.width", 200)
pd.set_option("display.max_columns", 20)

cutoff = "LIVE"
curr_date = dt.date.today()

ccyPairs = [
    "USDHKD", "USDSGD", "USDCNO", "USDKRW", "USDCNH", "USDIDR", "USDTHB",
    "USDPHP", "USDTWD", "USDJPY", "USDINR", "USDMYR", "USDCAD", "USDSEK",
    "USDNOK", "USDMYO", "USDIDO", "USDCHF", "USDTHO", "USDINF", "USDCNF",
    "USDILS", "USDCNY",
    "USDPLN", "AUDUSD", "GBPUSD", "EURUSD", "NZDUSD", "XAUUSD", "XAGUSD",
]

onshore_to_offshore = {"THO": "THB", "INF": "INR", "CNF": "CNO"}

# Z: → \\RVSG-FS01\shared
BBG_ROOT_LIVE = r"Z:\Business\Research\Dashboard\DataSources\BBG\FX"
BBG_ROOT_ASIA = r"Z:\Business\Research\Dashboard\DataSources\BBG_ASIA"

summary = []

for ccyPair in ccyPairs:
    bbg_id = ccyPair.replace("USD", "")
    if bbg_id in onshore_to_offshore:
        bbg_id = onshore_to_offshore[bbg_id]

    if cutoff in ("LIVE", "USA"):
        bbg_csv = os.path.join(BBG_ROOT_LIVE, bbg_id, f"FX_{bbg_id}.csv")
    else:
        bbg_csv = os.path.join(BBG_ROOT_ASIA, str(curr_date), "FX", bbg_id, f"FX_{bbg_id}.csv")

    exists = os.path.exists(bbg_csv)
    print("=" * 100)
    print(f"{ccyPair:8s}  ->  bbg_id={bbg_id:4s}  exists={exists}")
    print(f"  path: {bbg_csv}")

    if not exists:
        summary.append((ccyPair, bbg_id, False, None, None, None))
        continue

    try:
        bbg_data = pd.read_csv(bbg_csv)
        n_rows, n_cols = bbg_data.shape
        first_date = bbg_data.iloc[2, 0] if n_rows > 2 else None
        latest_date = bbg_data.iloc[3, 0] if n_rows > 3 else None
        print(f"  shape: {n_rows} rows x {n_cols} cols  |  latest row date: {latest_date}")
        print(bbg_data.head(5).to_string())
        summary.append((ccyPair, bbg_id, True, n_rows, n_cols, latest_date))
    except Exception as exc:
        print(f"  ERROR reading: {exc!r}")
        summary.append((ccyPair, bbg_id, True, None, None, None))

print("\n" + "=" * 100)
print("SUMMARY")
print("=" * 100)
summary_df = pd.DataFrame(summary, columns=["ccyPair", "bbg_id", "exists", "rows", "cols", "latest_row"])
print(summary_df.to_string(index=False))
