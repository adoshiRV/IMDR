# Feed: `barclays_skew`

Reference implementation of `EmailLinkedDownloadAcquirer`. Loads Barclays Trading / S&P Global normalised swaption-skew Excel files into `rates.fact_swaption_skew`.

## Quick facts

| | |
|---|---|
| **Feed name** | `barclays_skew` |
| **Vendor code** | `barclays` |
| **Transport** | Email-linked download |
| **Frequency** | Daily |
| **Sender** | `csa@barcap.com` |
| **Subject** | contains `SKEW BARCLAYS` |
| **Files per email** | 7 Excel files (USD × 3M/6M/9M/1Y/2Y/5Y/10Y expiries) |
| **Drop folder** | `data/skew/` |
| **Archive folder** | `data/skew/old/` |
| **Browser profile** | `data/browser_profiles/barclays/` |
| **DB tables** | `rates.dim_skew_surface`, `rates.fact_swaption_skew` |
| **Pipeline class** | `RatesSkewPipeline` |
| **Staleness pipeline name** | `rates.skew_barclays_daily` |
| **Scheduled** | `imdr_daily.py` PIPELINES, 08:00 SGT |

## Running manually

End-to-end (fetch + load + email):
```
python -m scripts.run_vendor_feed barclays_skew
```

Add `--headed` for SSO bootstrap (first run or after cookie expiry):
```
python -m scripts.run_vendor_feed barclays_skew --headed
```

Fetch only (no load):
```
python -m scripts.rates.barclays.rates_skew_download
```

Load only (ad-hoc / historical):
```
python -m scripts.rates.barclays.rates_skew_load
python -m scripts.rates.barclays.rates_skew_load --start 2026-04-01 --end 2026-04-14
```

## Credentials

```
IMDR_BARCLAYS_URL=https://live.barcap.com
IMDR_BARCLAYS_USERNAME=<user>
IMDR_BARCLAYS_PASSWORD=<password>
```

PingFederate SSO, no MFA at the moment. If MFA is later enforced, SSO must be re-bootstrapped with a device the token can bind to.

## Known quirks (from the original implementation)

- Server returns every download with `Content-Disposition: filename="data.xlsx"`. Spec uses `filename_from="anchor"` so files are named from anchor text ("USD 2Y Skew", etc.).
- Listing page lives inside `<iframe id="bcl-live-Iframe">`. `BrowserSession` iterates frames — do not change that.
- Before running the loader, clear any stale manual downloads like `data (N).xlsx` from `data/skew/` — they overlap with per-expiry files and cause MERGE violations on `uq_rates_fact_swaption_skew`.
- Exactly one SKEW BARCLAYS email per day. Spec picks the newest within `days_back=2`.
- Chrome cookie extraction via `browser-cookie3` does not work here (Chrome 127+ AppBound encryption); the persistent-profile approach is the only reliable path.

## Failure playbook

| Symptom | Likely cause | Fix |
|---|---|---|
| `NoEmailFound` daily | Vendor didn't send (holiday, outage) or moved to `csa@barclays.com` | Check Outlook manually; if the sender moved, update the spec |
| `SSOTimeout` | PingFederate cookies expired | Re-bootstrap headed |
| `ListingNotFound` | Portal page changed | Inspect the iframe in a headed session and update `listing_anchor_selector` |
| `DownloadFailed` on every file | Session invalidated mid-run | Re-bootstrap headed |
| Staleness alert for Rates Swaption Skew | Upstream skipped or load ran but loaded zero rows | Trace the RunReport JSONL under `{run_log_dir}/vendors/barclays_skew/` |

## Source pointers

- Spec: [src/imdr/vendors/specs/barclays_skew.py](../../../../src/imdr/vendors/specs/barclays_skew.py)
- Pipeline: [src/imdr/domains/rates/pipeline_skew.py](../../../../src/imdr/domains/rates/pipeline_skew.py)
- Schema doc: [docs/admin/rates/swaption_skew_schema.md](../../rates/swaption_skew_schema.md)
- Migration: `migrations/017_create_rates_swaption_skew.sql`
