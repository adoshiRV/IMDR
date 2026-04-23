# Vendors Framework — Architecture

## Why a framework at all

The Barclays SKEW pipeline was the catalyst: a daily email triggers an SSO-gated portal download, files land in `data/skew/`, and a separate loader reads them into SQL. The acquisition half was a 300-line one-off in `scripts/rates/barclays/rates_skew_download.py` — full of inline Outlook COM, Playwright setup, stale-Chrome-lock recovery, iframe polling, and safe-filename logic.

The problem: the next vendor will almost certainly need 80% of the same plumbing. Web-scrape vendors need the browser session. SFTP vendors need credential handling and idempotent archival. All of them need the same error taxonomy, success/failure email path, and staleness monitoring.

Rather than copy the script, the framework factors out the reusable parts and leaves each feed with a small, declarative spec.

## Boundary with existing layers

```
src/imdr/
  connectors/       protocol clients          (MSSQL, HTTPClient, CitiVelocityClient)
  vendors/          vendor-feed acquisition   (NEW — what we're documenting)
  domains/          ETL pipelines per domain  (BasePipeline subclasses)
  pipelines/        pipeline base + runner    (BasePipeline, health checks, audit)
  notifications/    email formatters          (success + new generic failure)
  reporting/        RunReport JSONL           (used by vendors runner)
  healthchecks/     post-load + staleness     (new StalenessSpec added per feed)
```

- **`connectors/` stays the "speak-a-protocol" layer.** `HTTPClient`, `CitiVelocityClient`, `MSSQLConnector` — they each wrap one transport. They don't know what a feed is.
- **`vendors/` sits on top and composes.** It knows "to get Barclays SKEW today I need to scan Outlook, then open a browser, then download files, then hand them to `RatesSkewPipeline`."
- **`domains/` and `pipelines/` are unchanged.** `RatesSkewPipeline` still runs the exact same extract→transform→load. The framework just supplies the files instead of assuming they're already on disk.

## The three composition seams

1. **Acquirer (`imdr.vendors.base.Acquirer` Protocol)** — produces `FetchResult` from nothing. One transport per acquirer module. New transports don't require framework changes.
2. **PipelineBuilder (`Callable[[files, connector, settings], BasePipeline]`)** — a tiny lambda that constructs the concrete domain pipeline. No subclassing, no mixin, no pipeline API change.
3. **Success context builder (optional)** — closes the parity gap with feeds that have rich success emails. Given the finished pipeline, returns extra kwargs for the success formatter.

These three keep the framework decoupled from any specific domain pipeline or email format.

## Why Protocol over ABC

The house style uses structural typing (`EmailFormatter` in `src/imdr/notifications/formatters/base.py`). Acquirers and sessions follow suit: `Acquirer`, `OutlookClient`, `BrowserSession` are Protocols. Tests substitute fakes by type; production uses the real impl. No inheritance ladder, no framework surgery when a new transport arrives.

## Error taxonomy

All acquirer failures raise a `VendorError` subclass. The runner translates any of them into a single failure-email path:

| Exception | Meaning |
|---|---|
| `NoEmailFound` | Outlook scan returned zero matches within the window |
| `LinkExtractionFailed` | Email matched but had no usable link |
| `SSOTimeout` | Browser waited past `sso_timeout_s` for the authenticated page |
| `ListingNotFound` | Authenticated page loaded but the expected anchors never appeared |
| `DownloadFailed` | All file downloads returned non-OK HTTP |
| `AcquirerMisconfigured` | Registry / spec wiring bug (duplicate name, unknown feed) |

`VendorError` itself is the base — catch that in user code if you want to handle any framework failure uniformly.

## Runtime lifecycle

```
run_vendor_feed_daily(name)
├── get_feed(name)  ──► VendorFeed
├── RunReport(pipeline_name=feed.staleness_pipeline_name)
│
├── Phase 1: acquire
│   └── feed.acquirer.fetch(headless, report)  ──► FetchResult
│       (on VendorError: report.error + _send_failure_email + return 1)
│
├── Phase 2: load
│   ├── MSSQLConnector()
│   └── feed.pipeline_builder(files, connector, settings).run()  ──► int rows
│       (on Exception: report.error + _send_failure_email + return 1)
│
├── Phase 3: success
│   ├── _archive_files(saved_files, output_dir/"old")
│   ├── _send_success_email(feed.success_formatter, **context)
│   └── return 0
│
└── finally:
    ├── report.finish()
    ├── report.flush_jsonl(run_log_dir/vendors/{feed}/...)
    └── connector.dispose()
```

## Testability

- No Playwright or win32com in the test suite — acquirer tests use `_FakeOutlook` + `_FakeBrowserSession` implementing the same Protocols.
- Registry tests exercise the import-side-effect contract directly.
- Runner tests mock the connector, email sender, and settings, then drive both success and failure paths.

See `tests/unit/test_vendors/` for the patterns.
