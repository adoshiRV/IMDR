# Web Scraping (Scaffold — Not Implemented)

Intended for vendors that require a login + navigate + download flow with no email trigger — e.g. Bloomberg / ICAP web terminals, where a daily CSV lives behind a nav path.

## Current status

`src/imdr/vendors/acquirers/web_scrape.py` has a `WebScrapeAcquirer` class that raises `NotImplementedError`. The class + spec shape are claimed so the next person implementing a web-scrape feed has an obvious place to start.

## Expected design

- Spec declares `login_url`, `target_url`, credential `prefix`, `output_dir`, `profile_name`.
- Acquirer uses `BrowserSession` (same one as email-linked downloads) — persistent Chrome profile, stale-lock recovery, iframe polling.
- Optional: submit credentials programmatically if the login form is simple (`page.fill + page.click`). Otherwise require a headed bootstrap just like email-linked.
- Download via `page.expect_download()` if the vendor uses `<a download>` anchors, or `ctx.request.get(href)` if file URLs are reachable via the authenticated cookie jar.

## Reuse

- `BrowserSession` — no changes needed.
- `VendorFetchFailureFormatter` — generic across all acquirer types.
- `register_feed`, `runner.run_vendor_feed_daily` — unchanged.

## When to implement

When the first web-scrape feed arrives. Resist the temptation to implement speculatively; we don't yet know which vendor-specific quirks need abstracting (CAPTCHA handling, anti-bot headers, paginated listings).
