# BBG Terminal Refresh — App Integration

How a downstream app (UI, model, internal tool, batch job) integrates with the
Bloomberg Terminal refresh system. Two roles to integrate as:

1. **Producer caller** — your app wants to *trigger* a fresh BBG pull.
2. **Consumer** — your app wants to *read* the data after it's been pulled.

If you're just running the script manually as a Terminal user, see
[terminal_python_setup.md](terminal_python_setup.md) instead.

---

## Architecture in one diagram

```
  ┌──────────────┐
  │  Your app    │
  └──────┬───────┘
         │  (1) trigger snapshot
         ▼
  ┌────────────────────────────────────────────────────┐
  │  refresh.py --user X --schedule snapshot           │
  │  (runs on a Terminal-logged-in PC)                 │
  └──────┬─────────────────────────────────────────────┘
         │  (2) writes
         ▼
  ┌────────────────────────────────────────────────────┐
  │  data/bloomberg/{user}/bbg_snapshot_{ts}.csv       │  ◄── (3a) read directly
  └──────┬─────────────────────────────────────────────┘
         │  (3b) IMDR watcher scans (every ~15 min)
         ▼
  ┌────────────────────────────────────────────────────┐
  │  IMDR SQL Server (fact_*)                          │  ◄── (3c) read via SQL
  └────────────────────────────────────────────────────┘
```

Pick (3a) when you need the freshest data and don't mind reading a CSV.
Pick (3c) when you can wait up to 15 minutes and want canonical SQL access.

---

## Role 1: Triggering a refresh from your app

### When to call

| Your trigger                 | Recommended `--schedule` |
| ---------------------------- | ------------------------ |
| User clicks "Refresh" button | `snapshot`               |
| Periodic background task     | `hourly` or `daily`      |
| One-off scripted update      | `snapshot`               |

Use `snapshot` for anything user-initiated — it pulls everything enabled for
that user, which is what the user expects when they "refresh."

### Subprocess example (Python)

```python
import subprocess
import sys

result = subprocess.run(
    [
        sys.executable,  # python.exe from the imdrbbg env
        r"Z:\Business\Personnel\Arjun\GitHub\IMDR\bloomberg\refresh.py",
        "--user", "dsuri",
        "--schedule", "snapshot",
    ],
    capture_output=True,
    text=True,
    timeout=120,  # BBG refdata is usually <5s; 120s is a generous safety
)

if result.returncode == 0:
    print("Refresh OK")
elif result.returncode == 2:
    print("Refresh PARTIAL (some tickers errored, snapshot still written)")
    print(result.stderr)
else:
    print(f"Refresh FAILED ({result.returncode})")
    print(result.stderr)
    raise RuntimeError("BBG refresh failed")
```

Make sure the subprocess is launched with the **`imdrbbg` env's
`python.exe`** — not the system Python. If your app uses a different env,
either:

- Activate `imdrbbg` first (`conda run -n imdrbbg python ...`), or
- Hard-code the path to the env's interpreter
  (`C:\Users\{user}\.conda\envs\imdrbbg\python.exe`).

### Subprocess example (PowerShell)

```powershell
$repo = "Z:\Business\Personnel\Arjun\GitHub\IMDR"
& conda run -n imdrbbg python "$repo\bloomberg\refresh.py" `
    --user dsuri `
    --schedule snapshot

if ($LASTEXITCODE -eq 0) {
    Write-Host "Refresh OK"
} elseif ($LASTEXITCODE -eq 2) {
    Write-Warning "Refresh PARTIAL"
} else {
    throw "BBG refresh failed (exit $LASTEXITCODE)"
}
```

### Exit codes

| Code | Meaning                                                                                      |
| ---- | -------------------------------------------------------------------------------------------- |
| `0`  | Success — all tickers pulled, file written, email sent (if configured).                       |
| `1`  | Setup/connection error — no Terminal, no `imdrbbg` env, or no matching rows in `tickers.csv`. |
| `2`  | Partial — some tickers errored individually. Snapshot still written with the successes.       |

### Flags your app should know about

| Flag         | When to pass                                                                                                |
| ------------ | ----------------------------------------------------------------------------------------------------------- |
| `--no-email` | Suppress the Outlook summary email. Use when your app sends its own notification, or for high-frequency runs. |
| `--dry-run`  | Plan only — parses `tickers.csv` and prints what *would* be pulled. No BBG call, no write, no email.        |

### Things your app **must not** assume

- That the user has the BBG Terminal logged in. Treat exit `1` as a normal failure mode, not a crash.
- That email will be sent. Email is gated by `IMDR_EMAIL_ENABLED` + `IMDR_EMAIL_TO` in `.env`. Best-effort only.
- That the user is at their desk. Snapshot mode is safe to call from a daemon, but if no Terminal is up, you get exit `1`.

---

## Role 2: Consuming refresh output

### Option A — read the CSV directly (fastest, raw)

After a successful refresh, the file is at:

```
Z:\Business\Personnel\Arjun\GitHub\IMDR\data\bloomberg\{user}\bbg_{schedule}_{YYYYMMDD}_{HHMMSS}.csv
```

Schema (long format, one row per ticker × field):

| Column           | Type          | Example                          |
| ---------------- | ------------- | -------------------------------- |
| `ticker`         | string        | `USGG10YR Index`                 |
| `terminal_user`  | string        | `dsuri`                          |
| `pulled_at_utc`  | ISO-8601 UTC  | `2026-06-02T14:23:17+00:00`      |
| `host`           | string        | `DSURI-PC01`                     |
| `domain`         | string        | `rates`                          |
| `field`          | string        | `PX_LAST`                        |
| `value`          | string        | `4.31`                           |

Atomicity: files appear via `.tmp` → rename. **Never read a `.tmp` file.**

To find the latest snapshot for a user:

```python
from pathlib import Path

user_dir = Path(r"Z:\Business\Personnel\Arjun\GitHub\IMDR\data\bloomberg\dsuri")
latest = max(user_dir.glob("bbg_snapshot_*.csv"), key=lambda p: p.stat().st_mtime)
```

### Option B — read from the IMDR SQL DB (canonical, deduped)

The IMDR cache scanner (runs every ~15 minutes) reads new files from
`data/bloomberg/{user}/` and appends to the appropriate `fact_*` table in
the `IMDR` database. Query it via the existing read-only mssql connection
(see [vscode_setup.md](../setup/vscode_setup.md)).

Idempotency key on the IMDR side: `(ticker, pulled_at_utc, terminal_user, field)`.
Re-scanning the same file is a no-op.

**Trade-off**: up to 15 minutes of latency vs. Option A. Use Option A only if
you specifically need sub-15-minute freshness.

---

## Common integration patterns

### Pattern 1 — "Refresh button" in a Tkinter / Electron / web UI

```
[User clicks Refresh]
       │
       ▼
Your app → subprocess(refresh.py --user X --schedule snapshot --no-email)
       │
       ▼
On exit 0  → glob latest data/bloomberg/X/bbg_snapshot_*.csv, parse, display.
On exit 2  → parse anyway, surface "some tickers failed" warning.
On exit 1  → "Terminal not available, please log in to Bloomberg."
```

Pass `--no-email` if your app's UI already shows success/failure — sending
duplicate email noise to a user every time they click Refresh is bad UX.

### Pattern 2 — Scheduled cross-product backtest run

```
nightly cron at 02:00 SGT
       │
       ▼
subprocess(refresh.py --user shared_term --schedule daily)
       │
       ▼
Wait for snapshot to land (poll for newest file), then run backtest pipeline.
```

For this, prefer reading from the IMDR DB (Option B) — by 02:30 the scanner
has long since ingested.

### Pattern 3 — High-frequency programmatic snapshots

Don't. If you need refresh more often than once per minute, you're using the
wrong abstraction — the refresh path uses `ReferenceDataRequest` snapshots,
not subscriptions. For tick / streaming data, talk to Arjun about a
`blpapi` subscription-mode pipeline. Bloomberg has daily caps per Terminal
on reference-data calls; hammering them gets the Terminal user throttled.

---

## Error handling cheat sheet

| Symptom                                            | Root cause                                  | Your app should…                                              |
| -------------------------------------------------- | ------------------------------------------- | ------------------------------------------------------------- |
| Exit `1`, stderr says `could not start a session`  | BBG Terminal off or not logged in           | Surface "Bloomberg Terminal not running" to the user.         |
| Exit `1`, stderr says `No enabled tickers`         | `tickers.csv` empty for this `(user, schedule)` | Surface "No tickers configured" — direct user to update CSV.  |
| Exit `1`, stderr says `blpapi is not installed`    | Subprocess didn't pick up the imdrbbg env   | Fix the subprocess invocation to use the right `python.exe`.  |
| Exit `2`                                           | Some tickers had `securityError` from BBG   | Parse the snapshot anyway; warn user about the failed ones.   |
| Subprocess times out                               | BBG Terminal frozen / network stalled       | Retry once; if still timing out, surface to user.             |
| File appears but is empty                          | You read a `.tmp` file or read mid-write    | Check the suffix is exactly `.csv`, not `.csv.tmp`.           |

---

## What about authentication / authorisation?

The producer (`refresh.py`) inherits the **Terminal user's authentication**
implicitly — whoever is logged into the Bloomberg Terminal on that PC is who
the API call is attributed to. There is no API key, no token, no scope.

Implications for your app:

- You can't programmatically pull data "as user X" if X isn't physically
  logged in at that workstation. The right pattern is: app on user X's PC →
  subprocess `refresh.py --user X`. Don't try to centralise the producer.
- `shared_term` is the catch-all login when no specific user is involved.
  Apps that aren't tied to a specific trader should default to
  `--user shared_term`.

---

## Where things go wrong, where to look

| Question                                      | Answer                                                           |
| --------------------------------------------- | ---------------------------------------------------------------- |
| Did the refresh actually run?                 | Check `data/bloomberg/{user}/` for a file with today's timestamp. |
| What did BBG return for a specific ticker?    | Open the CSV at the path above; filter to `ticker` and `field`.  |
| Did the email go out?                         | Check the inbox configured in `IMDR_EMAIL_TO`.                   |
| Did IMDR ingest the snapshot?                 | Query the relevant `fact_*` table for the latest `pulled_at_utc`. |
| Why did my subprocess hang?                   | BBG Terminal frozen, or the Terminal session is paused. RDP in. |

---

## See also

- [terminal_python_setup.md](terminal_python_setup.md) — installing `imdrbbg` on a user PC.
- [../../../bloomberg/README.md](../../../bloomberg/README.md) — the producer-side rules and design.
- [imdr_integration_plan.md](imdr_integration_plan.md) — consumer-side ingestion architecture.
- [vscode_setup.md](../setup/vscode_setup.md) — read-only SQL access (for Option B).
