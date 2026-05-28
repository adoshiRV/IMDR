# IMDR Vendors Framework

`src/imdr/vendors/` is the external-data acquisition layer. Every daily vendor feed — email-linked downloads today, web scrapes / SFTP / authenticated HTTP polls tomorrow — is defined as a small **spec** and registered once at import time. One generic runner drives the lifecycle: acquire → load → archive → email → run-log flush.

## When to use this framework

Use it when a feed needs to be **acquired** from an external source on a schedule. In practice that means anything that isn't a native Citi / BidFX API call already covered by a pipeline in `src/imdr/domains/`.

If the work is purely DB-resident (recompute, seeding, health checks), don't reach for this framework — it's specifically for the acquire-then-load shape.

## Architecture

```
scripts/run_vendor_feed.py  python -m scripts.run_vendor_feed <feed>
        │
        ▼
 imdr.vendors.runner.run_vendor_feed_daily(name)
        │
        ├─► registry.get_feed(name) ─► VendorFeed (spec + acquirer + pipeline_builder + formatter)
        │
        ├─► Phase 1: acquirer.fetch(headless, report) ─► FetchResult
        │        (raises VendorError on any acquisition failure)
        │
        ├─► Phase 2: pipeline_builder(files, connector, settings).run() ─► int rows
        │
        └─► Phase 3: archive files + send success email + flush RunReport JSONL
                 (on any failure: send VendorFetchFailureFormatter email, exit 1)
```

## Layers

| Layer | Module | Role |
|---|---|---|
| **Spec** | `imdr.vendors.specs.{vendor}_{feed}` | Declarative config — sender / subject / selectors / output paths |
| **Acquirer** | `imdr.vendors.acquirers.{transport}` | Implements the transport (email-linked, web scrape, SFTP, HTTP poll) |
| **Session** | `imdr.vendors.sessions.{outlook,browser,...}` | Protocol + production impl for each external system |
| **Feed** | `imdr.vendors.base.VendorFeed` | Binds acquirer + pipeline_builder + success formatter |
| **Registry** | `imdr.vendors.registry` | `VENDOR_FEEDS: dict[str, VendorFeed]`; populated at import time |
| **Runner** | `imdr.vendors.runner` | One function orchestrating the whole lifecycle |
| **CLI** | `scripts/run_vendor_feed.py` | Thin wrapper over the runner |

## Registered feeds

| Feed | Vendor | Transport | Schedule | Pipeline |
|---|---|---|---|---|
| `barclays_skew` | Barclays | Email-linked | Daily 08:00 SGT via `imdr_daily.py` | `rates.skew_barclays_daily` |

Use `python -m scripts.run_vendor_feed --list` to enumerate registered feeds at runtime.

## Vendor-specific documentation

| Vendor | Status | Docs |
|---|---|---|
| **Citi Velocity** | Live — primary vendor for rates, FX, equity, commodities | [citi/index.md](citi/index.md) |
| **Bloomberg (BBG)** via existing R pipeline on Z:\ | FX live as of 2026-04-25; other domains documentation-only | [bbg/index.md](bbg/index.md) |

## Key guarantees

- **Uniform error surface** — every acquirer raises `VendorError` subclasses (`NoEmailFound`, `SSOTimeout`, `ListingNotFound`, `DownloadFailed`, `LinkExtractionFailed`, `AcquirerMisconfigured`). The runner turns any of them into one failure email shape (`VendorFetchFailureFormatter`) regardless of transport.
- **One RunReport per run** — acquire + load share the same `RunReport(pipeline_name=feed.staleness_pipeline_name)` so ops sees a single JSONL per feed per day under `{run_log_dir}/vendors/{feed}/`.
- **Idempotent archival** — successfully-loaded files move to `{output_dir}/old/` with a UTC date suffix. Failure paths leave files in place for replay.
- **No Citi quota coupling** — framework has nothing to do with `TagQuotaTracker`; feeds here register in `imdr_daily.PIPELINES` with `estimated_tags: 0`.

## Onboarding a new feed

See [adding_a_vendor.md](adding_a_vendor.md) for the end-to-end checklist.

## Further reading

- [architecture.md](architecture.md) — why this shape, where it sits vs `connectors/` and `pipelines/`
- [email_linked_downloads.md](email_linked_downloads.md) — deep dive on the Barclays pattern
- [sso_and_sessions.md](sso_and_sessions.md) — persistent browser profile management
- [credentials.md](credentials.md) — `.env` conventions, vendor codes
- [troubleshooting.md](troubleshooting.md) — known failure modes
- [feeds/barclays_skew.md](feeds/barclays_skew.md) — operational notes for the reference feed
- [web_scraping.md](web_scraping.md) / [sftp.md](sftp.md) / [http_poll.md](http_poll.md) — planned transports
