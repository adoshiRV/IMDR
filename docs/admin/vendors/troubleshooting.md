# Troubleshooting

## Failure email landed — now what?

The framework sends one failure email per failed run using `VendorFetchFailureFormatter`. The email includes:

- Feed name, vendor code, phase (`acquire` or `load`)
- Exception type
- Exception message
- Run time (UTC + SGT)

Phase is the first clue:

| Phase | Likely category |
|---|---|
| `acquire` | Outlook, browser, or portal issue |
| `load` | Pipeline / DB / data issue — same as any other ETL failure |

Full detail is in the RunReport JSONL at `{run_log_dir}/vendors/{feed}/{feed}_{YYYYMMDD}_{HHMMSS}.jsonl`.

## `NoEmailFound`

> Acquirer scanned Outlook and returned zero matching emails.

Check in order:

1. Did the email actually arrive? Open Outlook, search the sender + subject manually.
2. Is the subject exactly what the spec expects? `subject_contains` is a case-insensitive substring — wide net on purpose, but a vendor can still rename a report.
3. Is the email within `days_back` of now? Default is 2 days — holidays can exceed that. One-off: re-run with a longer window.
4. Is Outlook running and signed in? `win32com.client.Dispatch("Outlook.Application")` relies on an available Outlook profile.

## `LinkExtractionFailed`

> Matching email found but no usable link.

The HTML body parser looks for a `<b>` with text matching `link_label`, then the next `<a href>`. If the vendor changed the template, either adjust `link_label` in the spec or update the parser in `sessions/outlook.py::_extract_labelled_link`.

## `SSOTimeout`

> Browser opened the portal link but the expected anchors never appeared within `sso_timeout_s`.

Almost always expired SSO cookies. Fix:

1. Re-bootstrap the profile headed — see [sso_and_sessions.md](sso_and_sessions.md).
2. Confirm the portal URL still works in a regular browser. Portals occasionally move.

## `ListingNotFound`

> Authenticated page loaded but the selector didn't match any anchors.

The vendor probably changed their listing layout. Open the portal headed, inspect the anchors with DevTools, update `listing_anchor_selector` in the spec. Also check that the listing wasn't moved into a new iframe — the session does poll every frame, but a single-frame page → multi-frame page transition needs no change (already supported).

## `DownloadFailed`

> Every anchor download returned a non-OK HTTP status.

If some anchors worked: those paths populate `FetchResult.warnings` but the fetch still succeeds. If all fail: usually a portal-side auth issue (expired cookies mid-session, rate limit, IP block). Re-bootstrap + retry.

## `AcquirerMisconfigured`

> Registry wiring problem — duplicate feed name or unknown feed requested.

Check `list_feeds()`: `python -m scripts.run_vendor_feed --list`. If your feed isn't there, `specs/__init__.py` may not import it. If it's listed twice, two specs registered the same name — rename one.

## Chrome profile won't open / `SingletonLock` errors

Stale Chrome locks. `BrowserSession` cleans them on entry, but if you're getting the error despite that, another Chrome against the same profile is probably actively running. Kill it:

```
taskkill /im chrome.exe /f
```

Then re-run. Never share a profile between two concurrent acquirer runs.

## Files not archiving after success

`_archive_files` only runs on the success path. If the runner returns non-zero, files stay in the drop folder for replay. Normal.

If the runner returned zero but files didn't move: check `{output_dir}/old/` actually exists and is writable.

## Staleness monitor shows my feed as stale despite a successful run

The staleness check queries `{table}.{date_column}` and compares to `max_stale_days`. If the feed successfully loaded zero rows — the acquirer fetched but the vendor's file contained no data — `fact_*.obs_date` didn't advance. Treat as an upstream data problem; the framework is doing its job.

## Related

- [index.md](index.md) — framework overview
- [architecture.md](architecture.md) — how the layers fit together
- [email_linked_downloads.md](email_linked_downloads.md) — pattern-specific gotchas
