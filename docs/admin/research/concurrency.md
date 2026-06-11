# Research ingest — parallel-vendor concurrency

Last updated: 2026-06-09

By default the orchestrator runs one vendor at a time (serial). Setting
`IMDR_RESEARCH_VENDOR_PARALLEL` or `--vendor-parallel` above `1` runs up to N
vendors concurrently inside a single `ingest_today.py` process.

---

## Knobs

| Knob | Type | Default | Hard cap | Effect |
|---|---|---|---|---|
| `IMDR_RESEARCH_VENDOR_PARALLEL` | env var | `1` | `3` | Max vendors running concurrently (outer loop). |
| `--vendor-parallel N` | CLI flag | inherits env var (default `1`) | `3` | Same as above; CLI overrides env. |
| `IMDR_RESEARCH_EMBED_CONCURRENCY` | env var | `4` | — | **Global** cap on simultaneous Voyage/Gemini embed-API calls (shared across all vendors in one orchestrator process). Lower if you see sustained 429s. |

If `--vendor-parallel` or the env var exceeds `3`, the orchestrator clamps it to `3`
and prints:

```
[WARN] --vendor-parallel=4 exceeds hard cap 3; clamping. See docs/admin/research/concurrency.md
```

The cap is deliberate: UBS Neo and Barclays each require a headed Chrome session
(~1.5 GB and ~1.2 GB RSS respectively). At N=3 worst-case, total Chrome RSS is
~3.5 GB plus ~1 GB Python = ~4.5 GB. Hosts with less headroom must stay at N=1 or N=2.

Source of truth: `_VENDOR_PARALLEL_HARD_CAP = 3` in
`playground/research/ingest_today.py`.

---

## How to enable parallel ingest

```bash
# N=2 — recommended first step
IMDR_RESEARCH_VENDOR_PARALLEL=2 python playground/research/ingest_today.py

# Equivalent via flag
python playground/research/ingest_today.py --vendor-parallel 2

# N=2 targeting specific vendors (comma-separated, no spaces)
IMDR_RESEARCH_VENDOR_PARALLEL=2 python playground/research/ingest_today.py --vendors goldman,ms,nomura

# Lower embed slots if you see Gemini 429 storms alongside vendor parallelism
IMDR_RESEARCH_VENDOR_PARALLEL=2 IMDR_RESEARCH_EMBED_CONCURRENCY=2 python playground/research/ingest_today.py
```

Default (serial, unchanged from pre-Phase-6 behaviour):

```bash
python playground/research/ingest_today.py
```

---

## What the operator sees

### Per-vendor log files

Every `_run_vendor` call writes to its own log file:

```
playground/research/logs/ingest_today/{YYYYMMDD}/{vendor}.log
```

Example for a run on 2026-06-09:

```
playground/research/logs/ingest_today/20260609/goldman.log
playground/research/logs/ingest_today/20260609/ms.log
playground/research/logs/ingest_today/20260609/barclays.log
```

Lines in the file carry a UTC timestamp; stdout does not (keeps it readable).
To follow one vendor's stream live while two others run alongside it:

```bash
tail -f playground/research/logs/ingest_today/20260609/goldman.log
```

Implementation: `playground/research/ingest/_vendor_log.py` (`VendorLogger`).

### Stdout prefix

Every vendor-scoped stdout line is prefixed `[{vendor}]`:

```
[goldman] discovered: 42 reports
[ms] discovered: 199 reports
[goldman] funnel: discovered=42  after_relevance_filter=38  ...
[ms] funnel: discovered=199  after_relevance_filter=140  ...
```

Global / orchestrator lines (run header, summary table) carry no prefix.

### Run header

The orchestrator prints the resolved `vendor_parallel` before launching:

```
========================================================================
  research ingest_today — all vendors
========================================================================
  vendors      : anz, barclays, bnp, db, goldman, hsbc, jpm, ms, nomura, socgen, stanc, ubs, westpac
  date window  : 2026-06-06 .. 2026-06-09
  parallel     : 1 PDFs per vendor, 2 vendor(s) concurrently
    realm 'rv-pingfed': barclays (serialised)
  limit        : no cap per vendor
  embed        : ON
  embed model  : gemini-embedding-2
```

---

## Auth realm gating

Some vendors share an identity provider. Concurrent logins from the same
IP/account within seconds can trigger IdP anomaly detection.

| Vendor | Auth realm |
|---|---|
| Barclays | `rv-pingfed` (RV PingFederate) |
| All others | independent (no realm) |

The orchestrator allocates a `asyncio.Semaphore(1)` per realm. Vendors in the
same realm are serialised relative to each other even if `vendor_parallel > 1`.
They can still run concurrently with vendors in other realms.

BofA is currently on PROD-HOLD (`project_bofa_onboarding.md`) but will also
join `rv-pingfed` when re-enabled. The realm gate will enforce serialisation
automatically without a code change.

Relevant code: `ingest_today.py` lines around `realms = {}` / `realm_sem`.

---

## One-orchestrator-per-host lock

Only one `ingest_today.py` process may run at a time on a host. On startup the
orchestrator acquires:

```
playground/research/.ingest_today.lock
```

using `filelock.FileLock(timeout=0)` — fail fast, no wait. If the lock is held
by a live process:

```
[ERR] Another ingest_today.py is already running on this host (lock held: .ingest_today.lock).
Wait for it to finish, or — if the prior run crashed — verify no live Python
process owns the lock before removing it.
```

### Recovery if the lock is misbehaving

`filelock` uses `msvcrt.locking` on Windows. The OS-level lock is released
automatically on process death, so a crashed run does NOT leave a permanent
lock. The `.lock` file on disk is just a flag file; what matters is whether a
process currently holds the OS handle.

Steps:

1. Check for a live process:
   ```powershell
   Get-Process python | Where-Object { $_.MainWindowTitle -eq "" } | Select-Object Id, StartTime, CPU
   ```
2. If a live ingest is running, wait for it.
3. If no Python process is holding the lock (crash scenario), delete the file:
   ```powershell
   Remove-Item playground/research/.ingest_today.lock
   ```
4. Re-run normally.

Do NOT delete the lock file while a live process is running — the process will
continue writing to the DB and OneDrive with no guard.

---

## Atomic PDF writes

PDFs are written by `safe_write_pdf` in `playground/research/ingest/upload.py`:

1. Write to `{target}.pdf.tmp`.
2. `os.replace(tmp, target)` — atomic on Windows NTFS.
3. Three retries on `PermissionError [WinError 32]` (OneDrive has the file
   open), with 1–2 s backoff + jitter.

If `target` already exists and its bytes differ from the incoming payload
(genuine vendor re-issue — same slug+uuid, new content), `safe_write_pdf`
**archives** the existing file to a dated sibling
`{stem}.{YYYYMMDD_HHMMSS}{suffix}` (using the existing file's mtime so the
archive name reflects when the prior bytes were captured), then writes the
new payload at the original path. A `[archive]` line is printed to the
per-vendor log noting the rename and the sha-prefix transition.

If two re-issues hit the same second (or two prior versions share an
mtime), the second archive name gets the first 8 chars of the existing
hash appended to disambiguate, so no archive ever silently clobbers another.

`PdfPathCollisionError` is now reserved for the (rare) case where the
archive rename itself fails — typically a permission error during
`os.replace(target -> archive)`. That state is genuinely ambiguous and
requires operator intervention.

Bytes-identical writes (idempotent retry) succeed silently.

---

## Soak ramp procedure

Ramp N=1 → 2 → 3. Each step requires ≥5 trading days of green before
proceeding. Full gate definitions and metric thresholds are in
`docs/admin/development/parallel_vendor_ingest.md` (soak gates table).

Quick summary of the gates:

| Check | Pass threshold |
|---|---|
| `ingest_today.py` exit code | `0` for 5 consecutive days |
| `IntegrityError` in any `{vendor}.log` | 0 occurrences |
| `PermissionError [WinError 32]` in any `{vendor}.log` | 0 occurrences |
| `asyncio.TimeoutError` from embed in any `{vendor}.log` | 0 occurrences |
| Total wallclock | ≤60% of week-prior median at N=1 |
| Per-vendor discovered→inserted ratio | within ±10% of N=1 baseline |

Any new failure mode at N=2 stops the ramp. Do not bump to N=3 until N=2
has 5 consecutive green days (see `feedback_slow_down.md`).

The production scheduler (`scripts/imdr_daily.py`) is NOT wired to a
non-default `vendor_parallel` value. The user controls the flip
(`feedback_no_prod_wiring_without_permission.md`).

---

## Troubleshooting

### 1. Lock contention — "Another ingest_today.py is already running"

Grep the per-vendor logs from the running process to see how far along it is:

```bash
tail playground/research/logs/ingest_today/$(date +%Y%m%d)/*.log
```

If no Python process is live (crash), follow the recovery steps above.

### 2. OneDrive `PermissionError [WinError 32]` exhaustion

`safe_write_pdf` retries 3× with jitter. If all three fail, the PDF is skipped
for this run (the report row is not inserted). Check:

```powershell
Get-Process OneDrive
```

OneDrive sync storms (large backlog, throttled upload) block the file handle
longer than the retry window allows. Options:

- Pause OneDrive sync, re-run `ingest_today.py`, resume sync.
- Reduce `vendor_parallel` so fewer PDFs land simultaneously.

The per-vendor log will show the `PermissionError` line and the target path.

### 3. `dim_tag` retry — silent under normal operation

`_upsert_tag_autocommit` in `ingest/db.py` catches `IntegrityError` and
re-SELECTs without emitting a log line — the race is expected and recoverable
at low frequency. You will NOT see a per-retry message in `{vendor}.log`.

If you suspect a sustained retry storm (e.g. via SQL Server profiler showing
many failed inserts on `research.dim_tag`), the mitigation is the same:
reduce `vendor_parallel`, or switch to the `MERGE WITH (HOLDLOCK)` fallback
documented in the design doc. There is no symptom in the operator-visible
logs today; revisit if a real incident surfaces and we need diagnostics.

### 4. IdP realm collision — dormant today; flips on when BofA is un-held

Barclays is currently the only vendor in the `rv-pingfed` realm. With one
member, the realm gate is a no-op. When BofA comes off PROD-HOLD
(`project_bofa_onboarding.md`) the gate will serialise the two login flows
automatically.

If you see a Barclays login failure under `vendor_parallel >= 2`, check the
realm header in the run banner — Barclays should still be the only member.
If a future code change adds a second `rv-pingfed` vendor and login windows
appear to overlap, file a bug — the realm semaphore should prevent it.

### 5. Gemini 429 storm — embed phase stalls

Symptoms: many `sleeping ~65s + jitter...` lines across multiple vendor logs
at the same time. The cross-vendor embed semaphore
(`IMDR_RESEARCH_EMBED_CONCURRENCY`) limits total in-flight embed calls, but all
vendors share the same Gemini quota.

Fix:

```bash
IMDR_RESEARCH_EMBED_CONCURRENCY=2 python playground/research/ingest_today.py --vendor-parallel 2
```

Or drop back to `vendor_parallel=1` until the quota window resets. The jitter
in `_sleep_with_jitter` (0–30 s uniform, `embed.py`) spreads recoveries but
cannot eliminate the storm if per-vendor volume is high.
