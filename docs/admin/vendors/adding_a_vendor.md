# Adding a New Vendor Feed

End-to-end checklist for onboarding a new daily vendor feed into the framework.

## 1. Confirm the feed shape

Pick the transport:

| Shape | Acquirer | Status |
|---|---|---|
| Email arrives daily → link → authenticated portal listing → download | `EmailLinkedDownloadAcquirer` | Implemented |
| Login page → navigate → download (no email trigger) | `WebScrapeAcquirer` | Scaffold only — see [web_scraping.md](web_scraping.md) |
| File drop on SFTP endpoint | `SFtpAcquirer` | Scaffold only — see [sftp.md](sftp.md) |
| Authenticated REST poll | `HttpPollAcquirer` | Scaffold only — see [http_poll.md](http_poll.md) |

If the shape doesn't exist yet, implement the acquirer under `src/imdr/vendors/acquirers/` following the `Acquirer` Protocol in `src/imdr/vendors/base.py`.

## 2. Seed the vendor in `dim_vendor` (if new)

Check `docs/admin/reference/dim_vendor.md` for the current seeds. If your vendor isn't there, add it via a follow-up migration. The vendor code you use in the spec must match `dbo.dim_vendor.vendor_code` — `resolve_vendor_id()` will fail loudly otherwise.

## 3. Add credentials to settings + `.env`

In `src/imdr/config/settings.py`, add fields prefixed with the vendor name:

```python
myvendor_url: str = "https://portal.myvendor.com"
myvendor_username: str = ""
myvendor_password: str = ""
```

Populate in `.env` as `IMDR_MYVENDOR_USERNAME=...` etc.

Acquirers that need credentials call `get_vendor_credentials("myvendor")` from `imdr.vendors.credentials`.

## 4. Write the spec

Create `src/imdr/vendors/specs/{vendor}_{feed}.py`. Use [barclays_skew.py](../../../src/imdr/vendors/specs/barclays_skew.py) as the template:

```python
from imdr.vendors.acquirers.email_linked import EmailLinkedDownloadAcquirer, EmailLinkedDownloadSpec
from imdr.vendors.base import VendorFeed
from imdr.vendors.registry import register_feed
from imdr.vendors.helpers import resolve_vendor_id

SPEC = EmailLinkedDownloadSpec(
    name="myvendor_myreport",
    vendor_code="myvendor",
    sender="reports@myvendor.com",
    subject_contains="DAILY REPORT",
    link_label="Download",
    listing_anchor_selector='a[href*="/download"]',
    output_dir=Path("data/myreport"),
    profile_name="myvendor",
)

def _build_pipeline(files, connector, settings):
    return MyReportPipeline(
        connector=connector, settings=settings,
        file_paths=files,
        vendor_id=resolve_vendor_id(connector, "myvendor"),
    )

register_feed(VendorFeed(
    name="myvendor_myreport",
    vendor_code="myvendor",
    acquirer=EmailLinkedDownloadAcquirer(SPEC),
    pipeline_builder=_build_pipeline,
    success_formatter=MyReportIngestFormatter(),
    staleness_pipeline_name="myreport.myvendor_daily",
))
```

## 5. Import the spec in `specs/__init__.py`

One line — imports trigger registration:

```python
from imdr.vendors.specs import myvendor_myreport  # noqa: F401
```

## 6. Register in the daily batch

Append to `PIPELINES` in `scripts/imdr_daily.py`:

```python
{"cmd": ["python", "-m", "scripts.run_vendor_feed", "myvendor_myreport"], "estimated_tags": 0},
```

`estimated_tags: 0` unless the feed also touches Citi (none currently do).

## 7. Add a staleness spec

Append a `StalenessSpec` in `src/imdr/healthchecks/staleness.py` `DEFAULT_SPECS` — `pipeline_name` must match the feed's `staleness_pipeline_name`:

```python
StalenessSpec(
    domain="My Report",
    pipeline_name="myreport.myvendor_daily",
    table="[myreport].[fact_obs]",
    date_column="obs_date",
    key_column="surface_id",
    dim_table="[myreport].[dim_surface]",
    dim_join_col="id",
    dim_label_cols=("some_col", "other_col"),
    max_stale_days=3,
),
```

Update `tests/unit/test_staleness.py::TestDefaultSpecs::test_expected_domains_covered` to include the new pipeline name.

## 8. Bootstrap SSO (email-linked / web-scrape only)

Before the first daily run:

```
python -m scripts.run_vendor_feed myvendor_myreport --headed
```

Complete SSO manually in the headed Chrome window. Session persists in `data/browser_profiles/{profile_name}/`. Subsequent runs are headless and silent.

## 9. Write operational notes

Create `docs/admin/vendors/feeds/{feed}.md`. Include at minimum:
- What the feed delivers and at what frequency
- Expected email/portal characteristics (sender, subject format, number of files)
- Re-bootstrap procedure if SSO expires
- Any feed-specific quirks

## 10. Tests

For most email-linked feeds, the existing `tests/unit/test_vendors/test_email_linked_acquirer.py` already covers the transport. Add feed-specific tests only if the spec has non-trivial logic (custom filename rules, unusual selectors, multiple emails per run, etc.).

## 11. Verify end-to-end

- Unit suite: `pytest tests/unit --ignore=tests/unit/test_config.py`
- Import check: `python -c "from imdr.vendors import list_feeds; print(list_feeds())"`
- Dry run: `python -m scripts.run_vendor_feed myvendor_myreport --headed`
- Staleness check: `python -m scripts.imdr_staleness_check`

Done — the feed now runs daily at 08:00 SGT and surfaces in the post-batch staleness email if the upstream goes silent.
