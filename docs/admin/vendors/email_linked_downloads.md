# Email-Linked Download Pattern

The `EmailLinkedDownloadAcquirer` implements the pattern used by Barclays Live SKEW and similar vendor feeds: vendor sends a daily email with a link to an SSO-gated portal listing, and the listing contains the actual download URLs.

## Flow

```
Outlook Inbox
  └── newest "SKEW BARCLAYS" from csa@barcap.com (last 2 days)
         │
         ├── html_body → BeautifulSoup → <b>View Excel:</b> next <a href=...>
         │        │
         │        └── unwrap_safelinks() — strips Microsoft Defender wrapper
         │
         ▼
Persistent-profile Chrome (Playwright)
  ├── SSO cookie from profile dir (bootstrapped headed, reused headless)
  ├── goto(link_url)
  ├── wait for frame containing anchors matching listing_anchor_selector
  │     (listings live in same-origin <iframe>; iterate page.frames)
  ├── ctx.request.get(href) for each anchor — uses session cookies
  └── write body to output_dir, filename from anchor text

saved_files: list[Path] → FetchResult
```

## Spec parameters

`EmailLinkedDownloadSpec` in `src/imdr/vendors/acquirers/email_linked.py`:

| Field | Purpose |
|---|---|
| `name` | Registry key, e.g. `"barclays_skew"` |
| `vendor_code` | FK to `dbo.dim_vendor.vendor_code` |
| `sender` | Email sender address filter |
| `subject_contains` | Case-insensitive substring filter on subject |
| `link_label` | Bold label preceding the target link in the email body, e.g. `"View Excel"` |
| `listing_anchor_selector` | CSS selector for anchors in the portal frame, e.g. `'a[href*="/rare/retrieve"]'` |
| `output_dir` | Where downloaded files land |
| `profile_name` | Sub-dir under `settings.browser_profile_root` |
| `filename_from` | `"anchor"` (derive from anchor text) or `"server"` (use Content-Disposition) |
| `days_back` | Outlook scan window in days |
| `newest_only` | Download only the newest matching email (default True) |
| `sso_timeout_s` | Browser wait timeout for listing anchors |

## Gotchas (learned the hard way on Barclays)

### 1. Defender Safelinks wrapping
Microsoft 365 rewrites outbound links inside emails. The acquirer unwraps the real URL from the `url=` query param via `_unwrap_safelinks()` in `sessions/outlook.py`. Don't try to use the wrapped URL directly — the session cookies won't carry.

### 2. Listings live inside iframes
Barclays Live puts the file list inside `<iframe id="bcl-live-Iframe">`. `page.locator(selector)` on the top frame returns nothing. `BrowserSession.download_anchors` iterates every frame and polls for the selector — do not short-cut this.

### 3. `Content-Disposition: filename="data.xlsx"` trap
Barclays returns the same server filename (`data.xlsx`) for every file. Always use `filename_from="anchor"` (the default) so the anchor text (e.g. "USD 2Y Skew") becomes the filename.

### 4. Stale Chrome singleton locks
If Chrome gets killed uncleanly (OS reboot, Task Scheduler cancel), it leaves `SingletonLock`, `SingletonCookie`, `SingletonSocket`, `lockfile` in the profile and refuses to start. `BrowserSession.__enter__` cleans these proactively.

### 5. First run must be headed
Playwright can't complete interactive SSO in headless mode. Bootstrap once with `python -m scripts.run_vendor_feed <feed> --headed` so the user can click through SSO; the session then persists and headless works.

### 6. Manual file drops break archival
If an operator manually drops an Excel into the drop folder (e.g. `data (1).xlsx`) between runs, the loader will try to process it alongside the acquired files. Clean stray files from the drop folder before a manual replay.

### 7. Re-running the acquirer is NOT idempotent on disk
Filenames include a `{YYYYMMDD_HHMMSS}` timestamp from `datetime.now()`, so each run creates new files. This is fine because the runner archives everything after load. If you run the acquirer twice without running the loader, you'll get duplicate files in the drop folder — loader dedups at the DB level (MERGE upsert) but processes both, which is wasteful.

## Error surface

| Exception | When |
|---|---|
| `NoEmailFound` | No matching emails in the Outlook window |
| `LinkExtractionFailed` | Email matched but contained no usable `<a>` under the bold label |
| `SSOTimeout` | Browser waited past `sso_timeout_s` without anchors appearing — usually means the profile's SSO cookies expired |
| `ListingNotFound` | Authenticated page loaded but the selector never matched — portal layout may have changed |
| `DownloadFailed` | All anchor downloads returned non-OK HTTP; partial failures accumulate `warnings` and still succeed |

## Reference feed: Barclays SKEW

- Spec: [src/imdr/vendors/specs/barclays_skew.py](../../../src/imdr/vendors/specs/barclays_skew.py)
- Ops notes: [feeds/barclays_skew.md](feeds/barclays_skew.md)
