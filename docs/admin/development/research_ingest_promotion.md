# Promote the research ingest package out of gitignored playground

**Status: PLANNED (2026-09-28).** Approved by the user, deferred to a dedicated
pass because the package is larger and more load-bearing than it looks.

---

## 1. Why

The entire research ingest pipeline — both lanes, portal and email — lives in
`playground/research/`, which is **gitignored**. The tests are tracked; the code
they test is not.

This is not hypothetical risk. It has already cost 85 days of data:

> `scripts/imdr_research.py` was rewritten on 2026-06-23 with the two email
> steps. It was never committed. A working-tree revert on 2026-07-01 removed
> them, the scheduled task carried on running the portal lane, and the email
> lane was dark until 2026-09-28. `git log -S "email-stage" --all` returns
> nothing — there was no commit to revert to and no diff to notice.

The orchestrator itself is now tracked and committed (`8610750`), which closes
that exact failure. The package behind it is still exposed.

It also violates the standing rule: `playground/` is for exploration; prod code
belongs in `scripts/`, libraries in `src/imdr/`. This package has been carrying
production data into `research.dim_report` for months.

## 2. Scale (measured, not estimated)

| | |
|---|---|
| modules | **61** (`ingest/*.py` + `ingest/classifiers/*.py`) |
| lines | **21,615** |
| entry scripts | `ingest_today.py` (portal), `ingest_outlook.py` (email), `retrieve.py`, `outlook/outlook_mapi_pull.py`, + the `_`-prefixed one-offs |
| tracked tests already importing it | `tests/unit/research/*` via `sys.path` insert |

The shared core — `db.py`, `chunk.py`, `embed.py`, `qdrant_writer.py`,
`relevance.py`, `upload.py`, `paths.py`, `pipeline.py`, `models.py` — is used by
**both** lanes. The portal lane runs every 3h and is healthy; it is the thing
most at risk from a careless move.

## 3. Proposed shape

```
src/imdr/research/ingest/          <- the shared library (db, chunk, embed,
                                      qdrant_writer, relevance, upload, paths,
                                      pipeline, models, classifiers/, filters/)
scripts/research/ingest_today.py   <- portal entry point
scripts/research/ingest_outlook.py <- email entry point
scripts/research/outlook/          <- producer + the one-off tools
```

The vendor crawlers (`crawler_*.py`, ~15 modules, the bulk of the line count)
are a judgement call: they are library-ish but change often and carry
vendor-specific scraping. Either `src/imdr/research/ingest/crawlers/` or leave
them adjacent to the entry scripts. **Decide before starting**, not midway.

## 4. Method

1. Move with `git mv` where already tracked, plain add where not, so history
   survives what little of it exists.
2. Rewrite imports. The package is imported as top-level `ingest.*` via a
   `sys.path` insert; under `src/` it becomes `imdr.research.ingest.*`. Every
   entry script and every `tests/unit/research/*` file that does the `sys.path`
   dance needs updating.
3. Consider a thin re-export shim at the old path for one release so an
   un-migrated one-off script does not silently break. Delete it deliberately.
4. Check `.gitignore` — `playground/*` is ignored wholesale; confirm nothing
   under the new paths is caught by another rule (`migrations/*` is ignored on
   purpose, see below).

## 5. Verification — the part that must not be skipped

A green test suite is **not** sufficient. The failure mode this whole exercise
exists to prevent is "looks healthy, is dead".

1. Full unit suite. Baseline is **13 pre-existing failures** plus 2 in
   `test_build_spider_html.py`; anything beyond that is yours.
2. Run the **portal** lane end to end and confirm it still writes rows:
   `python -m scripts.imdr_research --only portal-research` (~20 min).
3. Run the **email** lane end to end:
   `python -m scripts.imdr_research --only email-stage,email-ingest`.
4. `python -m scripts.research.check_research_freshness` — must exit 0.
5. `python playground/research/outlook/_reconcile_qdrant.py` — no drift.
6. Only then commit.

## 6. Notes for whoever picks this up

* **Migrations are gitignored on purpose** (`.gitignore:38`, "tracked via DBA
  channel, not git"). All 133 of them. Do not "fix" this as part of the move.
  Its real cost is collision: migration numbers get picked independently with
  nothing to catch a clash. **130 is taken** (email-only vendors, applied
  2026-09-28); BidFX Nexus needs **133**.
* `playground/research/outlook/staging/` accumulates and is rescanned in full
  every run — a live run currently reports `ingestable=585 db-dedup=291`, i.e.
  ~580 wasted checks per cycle. Archiving ingested staging JSON by date is a
  natural companion task but is **not** required for the move.
* Related: `outlook_local_mapi_producer.md` §11 (the 85-day outage post-mortem,
  the locale and HWM defects, the country-scan rewrite).
