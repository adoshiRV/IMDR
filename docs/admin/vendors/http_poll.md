# Authenticated HTTP Poll (Scaffold — Not Implemented)

Intended for REST feeds that don't fit the bespoke single-service clients in `src/imdr/connectors/` — e.g. S&P Global, ICE, or any vendor exposing a small REST API for daily data pulls.

## Current status

`src/imdr/vendors/acquirers/http_poll.py` has a placeholder `HttpPollAcquirer` that raises `NotImplementedError`.

## Boundary with `connectors/`

`src/imdr/connectors/citi_velocity.py` and `http.py` already wrap specific APIs. Don't reach for `HttpPollAcquirer` if a vendor has a rich API that deserves its own connector class — build a connector.

`HttpPollAcquirer` is for the case where the API is small (a handful of fixed paths, simple auth) and the acquire-then-load shape fits the daily vendor-feed pattern.

## Expected design

- Spec declares `base_url`, `paths: tuple[str, ...]`, `output_dir`, `credentials_prefix`.
- Acquirer uses `imdr.connectors.http.HTTPClient` with credentials from `get_vendor_credentials(prefix)`.
- For each path: `client.get_json(path)` → write JSON body to `{output_dir}/{path-slug}_{timestamp}.json`.
- Return `FetchResult` with the written files.
- Map HTTP 4xx to `AcquirerMisconfigured` (bad auth / unknown path) and 5xx to `DownloadFailed` (transient).

## When to implement

When the first small-REST vendor arrives. Keep it thin — if the API grows into something requiring OAuth refresh, rate limits, pagination etc., graduate it to a first-class `connectors/{vendor}.py` client.
