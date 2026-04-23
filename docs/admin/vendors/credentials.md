# Credential Conventions

## Environment variables

Every vendor credential follows the `IMDR_{VENDOR}_{FIELD}` pattern in `.env`:

```
IMDR_BARCLAYS_URL=https://live.barcap.com
IMDR_BARCLAYS_USERNAME=doshiarj
IMDR_BARCLAYS_PASSWORD=...
```

These bind to lower-cased fields on `Settings` (`barclays_url`, `barclays_username`, `barclays_password`).

## Accessing credentials from an acquirer

```python
from imdr.vendors.credentials import get_vendor_credentials

creds = get_vendor_credentials("barclays")  # prefix = lowercased vendor name
creds.username  # "doshiarj"
creds.password  # "..."
creds.url       # "https://live.barcap.com"
```

Unset fields return empty strings. Acquirers check what they need.

## Vendor codes vs settings prefixes

Two names, both lowercase, usually identical:

- **Vendor code** — FK value in `dbo.dim_vendor.vendor_code`. Used by `resolve_vendor_id()` to look up the surrogate `vendor_id` for fact rows.
- **Settings prefix** — the stem of the `IMDR_{PREFIX}_*` env vars.

For Barclays both are `"barclays"`. When they need to differ (e.g. a vendor re-brands mid-flight), the spec can set `vendor_code` and the credentials lookup independently.

Current seeds in `dim_vendor` (migration 018):

| vendor_code | vendor_name |
|---|---|
| `citi_velocity` | Citi Velocity |
| `barclays` | Barclays Live |
| `bidfx` | BidFX |
| `bloomberg` | Bloomberg |

New vendors → add a migration that inserts into `dbo.dim_vendor` and keep the `vendor_code` stable forever (fact-table FKs depend on it).

## Rotation

Password rotations:

1. Update `.env` with the new value.
2. Restart any long-running process that reads settings.
3. Re-bootstrap any persistent browser profile that holds a session using the old credential — see [sso_and_sessions.md](sso_and_sessions.md).

The framework does not push credentials to vendor portals; it only makes them available to acquirers that need them.

## Related

- [../dim_vendor.md](../dim_vendor.md) — full vendor-dimension schema
- [sso_and_sessions.md](sso_and_sessions.md) — bootstrap / profile management
