# A1 — Symbol Callgraph & Dead-Module Report

- **Filed**: 2026-05-14
- **Scope**: every `.py` in `src/imdr/` and `scripts/`
- **Modules scanned**: 307
- **Source modules** (`imdr.*`): 201
- **Script modules** (`scripts.*`): 106

## Method

AST walk of every file → record top-level public symbols + import statements →
compute longest-prefix module match → invert to in-edges. Relative imports skipped
(use `git grep` for those). Top-level scripts with no callers are NOT dead — they
are entry points if they have `if __name__ == "__main__"` or are referenced from
scheduler scripts; that check is downstream.

## Source modules with zero internal callers (18)

These are `src/imdr/**` modules that no other `imdr.*` module imports.
Treat as **delete candidates** unless they're:
- Imported by a script (cross-check with scripts list below)
- An entry point themselves (rare under `src/`)
- A plugin / registry-loaded module (e.g., vendor specs auto-discovered)

| Module | Path | Exports |
|---|---|---|
| `imdr.data_access` | [src/imdr/data_access.py](src/imdr/data_access.py) | IMDRData |
| `imdr.domains.commodities.clean_implied_vol` | [src/imdr/domains/commodities/clean_implied_vol.py](src/imdr/domains/commodities/clean_implied_vol.py) | TABLE, HardBoundViolationRule, RobustOutlierRule, PercentageChangeRule |
| `imdr.domains.fx.pipeline_ohlc` | [src/imdr/domains/fx/pipeline_ohlc.py](src/imdr/domains/fx/pipeline_ohlc.py) | FXOHLCPipeline |
| `imdr.domains.rates.discovery` | [src/imdr/domains/rates/discovery.py](src/imdr/domains/rates/discovery.py) | RatesTagDiscovery |
| `imdr.healthchecks.anomaly` | [src/imdr/healthchecks/anomaly.py](src/imdr/healthchecks/anomaly.py) | log, AnomalyRecord, AnomalyDetector |
| `imdr.market_calendar.cb_events` | [src/imdr/market_calendar/cb_events.py](src/imdr/market_calendar/cb_events.py) | upcoming_cb_events, recent_cb_events, rate_decisions, events_for_currency |
| `imdr.market_calendar.events` | [src/imdr/market_calendar/events.py](src/imdr/market_calendar/events.py) | MarketEvent, market_events_for_date |
| `imdr.notifications.formatters.anomaly_alert` | [src/imdr/notifications/formatters/anomaly_alert.py](src/imdr/notifications/formatters/anomaly_alert.py) | AnomalyAlertFormatter |
| `imdr.notifications.formatters.polywatch_alert` | [src/imdr/notifications/formatters/polywatch_alert.py](src/imdr/notifications/formatters/polywatch_alert.py) | POLYMARKET_EVENT_URL, ALERT_CLASS_ORDER, ASSET_TAG_ORDER, ASSET_TAG_LABELS, MAX_UNCURATED_PER_EMAIL … |
| `imdr.queries.fx` | [src/imdr/queries/fx.py](src/imdr/queries/fx.py) | OHLC_RANGE_STATS, LATEST_BY_SYMBOL |
| `imdr.reporting.reporter` | [src/imdr/reporting/reporter.py](src/imdr/reporting/reporter.py) | log, AppendVerification, SuccessReport, PipelineReporter |
| `imdr.schemas.audit` | [src/imdr/schemas/audit.py](src/imdr/schemas/audit.py) | PipelineRunCreate, PipelineRunUpdate, PipelineRunResponse |
| `imdr.schemas.frequency` | [src/imdr/schemas/frequency.py](src/imdr/schemas/frequency.py) | FrequencyResponse |
| `imdr.schemas.vendor` | [src/imdr/schemas/vendor.py](src/imdr/schemas/vendor.py) | ALLOWED_VENDOR_TYPES, VendorCreate, VendorResponse |
| `imdr.vendors.acquirers.http_poll` | [src/imdr/vendors/acquirers/http_poll.py](src/imdr/vendors/acquirers/http_poll.py) | HttpPollSpec, HttpPollAcquirer |
| `imdr.vendors.acquirers.sftp` | [src/imdr/vendors/acquirers/sftp.py](src/imdr/vendors/acquirers/sftp.py) | SFtpSpec, SFtpAcquirer |
| `imdr.vendors.acquirers.web_scrape` | [src/imdr/vendors/acquirers/web_scrape.py](src/imdr/vendors/acquirers/web_scrape.py) | WebScrapeSpec, WebScrapeAcquirer |
| `imdr.vendors.credentials` | [src/imdr/vendors/credentials.py](src/imdr/vendors/credentials.py) | VendorCredentials, get_vendor_credentials |

## Script modules with zero internal callers (2)

Scripts often have no Python callers — they're invoked via `python -m scripts.X`
from schedulers. Cross-reference against `scripts/imdr_*.py` to confirm.

| Module | Path | Has `__main__` |
|---|---|---|
| `scripts.explore.probe_bidfx_tenors` | [scripts/explore/probe_bidfx_tenors.py](scripts/explore/probe_bidfx_tenors.py) | no |
| `scripts.explore.probe_bidfx_xau` | [scripts/explore/probe_bidfx_xau.py](scripts/explore/probe_bidfx_xau.py) | no |

## Top 20 most-imported modules

Sanity check: these should be foundational (`connectors.mssql`, `models.base`, etc.).

| Module | Caller count |
|---|---|
| `imdr.config.settings` | 101 |
| `imdr.connectors.mssql` | 74 |
| `imdr.utils.logging` | 36 |
| `imdr.connectors.citi_velocity` | 33 |
| `imdr.connectors.citi_helpers` | 30 |
| `imdr.connectors.reader` | 27 |
| `imdr.reporting.run_report` | 25 |
| `imdr.universe.fx` | 24 |
| `imdr.notifications.email` | 22 |
| `imdr.config.pipeline_config` | 21 |
| `imdr.universe.rates` | 20 |
| `imdr.connectors.citi_quota` | 19 |
| `imdr.healthchecks.base` | 19 |
| `imdr.healthchecks.checks` | 18 |
| `imdr.market_calendar.calendar` | 18 |
| `imdr.connectors.bulk` | 17 |
| `imdr.models.base` | 17 |
| `imdr.pipelines.base` | 17 |
| `imdr.healthchecks.cleaning` | 15 |
| `imdr.market_calendar.holidays` | 14 |