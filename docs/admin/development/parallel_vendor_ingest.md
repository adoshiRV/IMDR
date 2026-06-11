# Parallel vendor research ingest

- **Filed**: 2026-06-08
- **Status**: in progress (Phase 1 starting)
- **Triggered by**: 13 vendors live, 5+ more planned. Serial wallclock at the current cadence is ~50-90 min for a daily run; doubling the vendor count under the same loop is untenable.
- **Linear**: this doc is the system of design; status/ownership lives in Linear (project to be filed by `imdr-pm` after Phase 1 lands).

## Problem

`playground/research/ingest_today.py` runs vendors strictly serially (see the loop at ~L716). Each vendor spins up its own Playwright Chrome (or in-process headless ctx) against a vendor-unique persistent profile dir. Within a vendor, PDFs already run in parallel via `asyncio.gather` gated by an `asyncio.Semaphore(parallel)`. So the bottleneck is **across** vendors, not within.

Going parallel across vendors is feasible — profile dirs are per-vendor (no Chrome `SingletonLock` collision), Gemini quota is comfortably under tier-1 limits at our chunk volumes, and Qdrant is concurrency-safe in remote mode. But there are real concurrency hazards that have to be fixed first; left unfixed they cause silent data loss, not loud errors.

## Risks identified by audit

A six-agent audit (2026-06-08, see git log) catalogued the failure surfaces. The four classes that block flipping the switch:

1. **dim_tag SELECT-then-INSERT race** in `playground/research/ingest/db.py:144-161`. Two vendors emitting the same canonical tag (`MACRO`, `RATES`, author name) on overlapping seconds → second hits `IntegrityError` → entire report `engine.begin()` rolls back at `pipeline.py:200` → report + chunks silently dropped.
2. **Non-atomic PDF write** at `upload.py:89`. `write_bytes` direct to final path; OneDrive can produce silent `<file> (RV Capital's conflicted copy).pdf` siblings. Nothing reconciles them. `dim_report.pdf_path` may point at a truncated file while the good content sits in a conflicted-copy filename.
3. **LLM classifier cache JSON race** in `classifiers/llm.py:91-104`. Read-modify-write on shared JSON file with no lock — last-writer-wins silently drops cache entries. Currently dormant in prod (BofA held), but live code.
4. **Stdout / asyncio interleave**. `_console.py:36` reconfigures encoding but not line-buffering. Section headers and the results table will scramble under N>=2, with most "global" lines carrying no vendor tag. `asyncio.gather` without `return_exceptions=True` cancels siblings on first uncaught exception.

Secondary risks (don't block, but addressed in the same effort):

5. **Pool exhaustion** at N>=4. `pool_size=4, max_overflow=4` is right at the cap.
6. **Gemini 429 retry has no jitter** — synchronised retry storm under burst load.
7. **Auth realm bursts** — Barclays (+ BofA when un-held) both federate via RV PingFed; concurrent re-logins can trip IdP anomaly detection.
8. **RAM budget** at N=4 with two headed-Chrome vendors (UBS Neo, Barclays) crosses ~5 GB RSS for Chrome alone.

## Plan

Six implementation phases. Each phase = one PR. Each PR gets `imdr-code-reviewer` review; PRs touching creds/logs also get `imdr-security`. `imdr-doc-manager` runs once at the end.

### Phase 1 - DB race fix

- `playground/research/ingest/db.py`: new `_upsert_tag_autocommit(engine, ...)` runs in its own short txn (outside the report `begin()`), catches `IntegrityError`, re-SELECTs, returns id. Same shape for `_ensure_model_id`.
- `pipeline.py:200`: call new helper *before* opening the report `begin()`; pass `tag_ids` in.
- `_research_engine` in `ingest_today.py`: `pool_size=12, max_overflow=12`. Comment math: `1 conn/ingest_one * N=3 vendors * parallel=2 + 6 headroom`.
- **Reject** `MERGE WITH (HOLDLOCK)` as the default — it serialises every concurrent insert on hot keys (every classifier emits `MACRO`). Catch-and-retry is preferred. HOLDLOCK is the documented fallback if soak shows >1% retry rate.
- New `tests/unit/research/test_db_tag_race.py`: 8-thread upsert of same tag -> one row, no surfaced IntegrityError.

### Phase 2 - Atomic PDF write + orchestrator lock + slug hardening

- `upload.py:89`: new `safe_write_pdf(target, payload)` -> `target.with_suffix(".pdf.tmp")` -> `write_bytes(tmp)` -> `os.replace(tmp, target)` with 3x retry on `PermissionError` (1-2s backoff + jitter) for the OneDrive-has-it-open case.
- Path-collision check: if `target.exists()` and `size > 0`, re-hash; bytes match -> idempotent return; bytes differ -> **archive existing to `{stem}.{YYYYMMDD_HHMMSS}{suffix}` (using the existing file's mtime), then write new payload** (2026-06-11 change). Earlier behaviour raised `PdfPathCollisionError` on bytes-differ; that produced 50+ daily failures because vendors (notably DB) routinely re-issue the same slug+uuid with new bytes. `PdfPathCollisionError` is now reserved for the rare case where the archive rename itself fails. See `concurrency.md` for the full semantics.
- `paths.py:59`: **NOT widening** `_UUID_SHORT_LEN` after all. The reviewer's concern (8-char birthday collisions) is 1-in-4-billion-per-day; the real-world failure mode is OneDrive conflicted-copies on identical paths, fully addressed by atomic-write + hash-equality check below. Bumping to 12 would force a synchronized update in `backfill_classifier.py:83` (`_PATH_UUID_RE = r"_([A-Za-z0-9]{1,8})\.pdf$"`) which extracts the suffix from already-written 8-char paths. Out of scope. Revisit only if production corpus actually hits a birthday collision.
- New `ingest_today.py` startup: `filelock.FileLock("playground/research/.ingest_today.lock", timeout=0)` -> fail fast if another orchestrator is running. Documents "one orchestrator per host" as a hard constraint.
- **Drop** the v1 plan's startup `SingletonLock` sweep — Win + SMB make the PID detection flaky and `psutil` isn't a dep we want to add for this.
- New `tests/unit/research/test_safe_write_pdf.py`: concurrent same-bytes (both succeed), concurrent diff-bytes (one raises typed error), simulated OneDrive lock (retry then succeed).

### Phase 3 - Observability + asyncio hardening

- `_console.py:36`: add `line_buffering=True` to the `stdout.reconfigure(...)` call.
- New `VendorLogger(vendor_code, run_date)` writes to `playground/research/logs/ingest_today/{YYYYMMDD}/{vendor}.log` AND prefixes stdout with `[{vendor}]`. Operator can `tail -f` one vendor without buffering blocking live visibility.
- All "global" prints in `_run_vendor` route through the logger; `[start]` heartbeat keeps its existing format (already vendor-tagged).
- `_amain`: `asyncio.gather(*tasks, return_exceptions=True)` -> convert exceptions to synthetic `VendorRunSummary(error=...)`. The summary table survives partial failure.
- `main()` catches `KeyboardInterrupt` once, prints abort line, returns 130. **Do not** reach into Playwright internals — each crawler's existing `async with` cleanup runs on cancel.
- `_print_run_header` reflects the resolved `vendor_parallel`.
- **Reject** the v1 plan's per-vendor `StringIO` buffering — a stalled vendor would be invisible until completion. Live file + prefixed stdout gives both atomicity (per-file) and visibility (live tail).

### Phase 4 - Embed jitter + cross-vendor cap + LLM cache lock

- `embed.py`: lazy-init `asyncio.Semaphore(int(os.environ.get("IMDR_RESEARCH_EMBED_CONCURRENCY", "4")))` via `contextvars.ContextVar` on first `embed_chunks` call. **Do not** instantiate at module-import time — semaphores are loop-bound and would raise `Future attached to different loop` errors.
- Both providers: `await asyncio.sleep(_SLEEP + random.uniform(0, 30))` on 429. Extract `_retry_429(coro_factory, sleep_s, max_retries)` helper, used by Voyage + Gemini.
- `classifiers/llm.py`: wrap cache load/save in `filelock.FileLock(cache_path + ".lock")`. **Pick `filelock`**, not `portalocker` — pure-python, smaller surface, MIT-licensed. One new dep total (also used by Phase 2 orchestrator lock).
- New `tests/unit/research/test_embed_jitter.py`: two concurrent retries don't wake at the same millisecond. `test_llm_cache_concurrent.py`: two coroutines writing different keys both persist.

### Phase 5 - auth_realm field (no-op for now)

- Add `auth_realm: str | None = None` to `VendorSpec`; set `"rv-pingfed"` on Barclays.
- Orchestrator reads it but does nothing with it at N=1. Logged in the run header.
- **Defer to follow-up issue**: the actual realm-gate semaphore + Barclays re-login cooldown. Only matters when BofA comes off PROD-HOLD or N>=2 hits production.

### Phase 6 - Orchestrator wiring + flag

- `--vendor-parallel N` (env `IMDR_RESEARCH_VENDOR_PARALLEL`, default `1`, hard-cap **3**). Cap at 3 (not v1's 6) because RAM budget for UBS+Barclays at headed Chrome is real.
- Loop at `ingest_today.py:716` -> `asyncio.Semaphore(N)`-gated `asyncio.gather`.
- Extract `_run_vendor_with_session_fetch(vendor, refs, fetch_fn)` helper; collapse Barclays+SG if-elif at L526-557 into a `session_fetcher` callback on `VendorSpec`.
- `.env.example`: add `IMDR_RESEARCH_VENDOR_PARALLEL=1` with comment.
- **Do not** edit `scripts/imdr_daily.py` or any scheduler — flag stays off until user OKs the flip (no-prod-wiring rule).

### Phase 8 - Docs

`imdr-doc-manager` writes:

- `docs/admin/research/concurrency.md` — operator model, env vars, knobs, ramp procedure, what-if scenarios
- `docs/admin/research/scrapers/index.md` — add `auth_realm` column
- Append to this doc: links to merged PRs + final soak metrics
- `MEMORY.md` topic file `project_vendor_parallelism_live.md` once the soak passes
- **No** `docs/admin/updates/` entry — that directory is for consumer-impact schema/API changes; vendor parallelism is operational.

## Soak gates

Each ramp (N=1 -> 2 -> 3) waits >=5 trading days of green:

| Check | Threshold |
|---|---|
| `ingest_today.py` exit code | `0` for 5 consecutive days |
| New `IntegrityError` in `{vendor}.log` | `0` |
| New `PermissionError [WinError 32]` | `0` |
| New `asyncio.TimeoutError` from embed | `0` |
| Total wallclock | <=60% of week-prior median at N=1 |
| Per-vendor discovered->inserted ratio | within +/-10% of N=1 baseline |

Memory rule `feedback_slow_down` applies: any new failure mode at N=2 stops the ramp and triggers triage.

## RAM budget (sanity)

| Vendor | Mode | Approx RSS |
|---|---|---|
| UBS Neo | Headed Chrome | ~1.5 GB |
| Barclays | Headed Chrome + PingFed | ~1.2 GB |
| Others (10) | Headless Playwright | ~0.6-0.8 GB each |

At N=3 worst-case (UBS+Barclays+heavy headless): ~3.5 GB Chrome + ~1 GB Python = ~4.5 GB RSS. Workstation has headroom; prod host should be measured before its first non-N=1 run.

## Out of scope

- BofA re-enable (held per `project_bofa_onboarding.md`; revisit when re-enabled)
- The actual auth-realm gate logic (deferred — only Barclays is currently in `rv-pingfed`)
- Switching from JSON LLM cache to SQLite (filelock is sufficient; SMB makes SQLite fragile)
- Production scheduler wiring — user flips the switch
