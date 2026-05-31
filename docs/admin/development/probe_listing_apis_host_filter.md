# Follow-up: `probe_listing_apis.py` allowed-host filter is missing `barclays`, `bnp`, `hsbc`

- **Linear**: [IMD-40](https://linear.app/imdr/issue/IMD-40/probe-listing-apispy-allowed-host-filter-missing-barclaysbnphsbc) (Urgent)
- **Date filed**: 2026-05-31
- **Status**: open — urgent (silent data-suppressing bug; misleads the operator)
- **Priority**: P1
- **Triggered by**: JPM Phase 2 onboarding (2026-05-29) — agentic review of
  [`docs/admin/research/scrapers/jpm.md`](../research/scrapers/jpm.md) called
  out that the `--vendor` CLI flag I added would silently return "no listing
  API" for the three already-broken vendors.

## Problem

[`playground/research/probe_listing_apis.py`](../../../playground/research/probe_listing_apis.py)
has **two parallel registries** that need to stay in sync, and they don't:

1. **`VENDOR_HUBS` dict** (~L35–91) — the per-vendor hub URLs to visit.
   Current entries: `goldman`, `anz`, `nomura`, `ms`, `hsbc`, `barclays`,
   `bnp`, `jpm`.

2. **`allowed_host` chain inside `_capture()`** (~L126–138) — a hostname
   whitelist that decides whether an intercepted XHR response is kept or
   thrown away. Current entries: `matrix.ms.com`, `anz.com`, `nomura`,
   `gs.com`, `jpmorgan`.

`hsbc`, `barclays`, and `bnp` are in `VENDOR_HUBS` but their host
fragments (`research.hsbc.com`, `live.barcap.com`, `markets360.bnpparibas.com`)
are not in the `allowed_host` chain. When the probe runs against those
vendors, the headless Chrome opens the hub URL, the SPA fires its XHRs,
and **every response is silently dropped** by the host filter. Output
is an empty `listing_apis_top.txt` — looking like "the vendor returned
nothing" when really the script is discarding everything.

### Why it's worse now than yesterday

The 2026-05-29 JPM session added a `--vendor <code>` argparse flag so a
single vendor can be probed in isolation. Before that, the script always
ran every vendor and the working ones (`goldman` / `anz` / `nomura`)
produced output, so the broken vendors blended into the noise and went
unnoticed. With `--vendor barclays` you now get a clean-looking run
that returns nothing — looks like a real result, isn't.

## The fix

Three additional `elif` branches in the `allowed_host` chain:

```python
elif "barcap.com" in host:
    allowed_host = True
elif "bnpparibas.com" in host:
    allowed_host = True
elif "research.hsbc.com" in host:
    allowed_host = True
```

Pre-existing gap; the JPM session deliberately backed out a wider host-list
addition to avoid scope creep.

## Better fix (~30 min)

Drive both registries off a single per-vendor declaration so they can
never drift again. For example:

```python
@dataclass
class VendorProbe:
    code: str
    hubs: list[str]
    host_fragments: list[str]   # any of these in url.host => accept

VENDORS: list[VendorProbe] = [
    VendorProbe("goldman",  hubs=["https://marquee.gs.com/s/home", ...],     host_fragments=["gs.com"]),
    VendorProbe("anz",      hubs=["https://research.anz.com/...", ...],       host_fragments=["anz.com"]),
    VendorProbe("nomura",   hubs=["https://www.nomuranow.com/research/m/Home"], host_fragments=["nomura"]),
    VendorProbe("ms",       hubs=["https://ny.matrix.ms.com/..."],            host_fragments=["matrix.ms.com"]),
    VendorProbe("hsbc",     hubs=[...],                                       host_fragments=["research.hsbc.com"]),
    VendorProbe("barclays", hubs=[...],                                       host_fragments=["barcap.com"]),
    VendorProbe("bnp",      hubs=[...],                                       host_fragments=["bnpparibas.com"]),
    VendorProbe("jpm",      hubs=[...],                                       host_fragments=["jpmorgan"]),
]
```

`_capture` then takes `host_fragments` for the currently-probing vendor
and the registries are guaranteed to stay in sync.

## Watch-outs

- **Re-running existing probes** after the fix: `goldman`, `anz`,
  `nomura`, `ms` already produced good output before — the fix just
  makes the broken three start working. Don't blow away
  `playground/research/{vendor}_explore/listing_apis*.json` for the
  working vendors when re-running.
- **The `--vendor` flag**: introduced 2026-05-29 in the JPM session
  ([commit `e173726`](../../../docs/admin/research/scrapers/jpm.md)
  references it). Keep it — that's how a single-vendor re-run will be
  invoked while testing the fix.

## Done when

- [ ] `allowed_host` chain (or the better-fix registry) accepts
  `barcap.com`, `bnpparibas.com`, `research.hsbc.com`.
- [ ] `python playground/research/probe_listing_apis.py --vendor barclays`
  returns a non-empty `listing_apis_top.txt`.
- [ ] Same for `--vendor bnp` and `--vendor hsbc`.
- [ ] Each of the three vendors gets a documented top-scoring listing API
  in [`docs/admin/research/scrapers/{vendor}.md`](../research/scrapers/)
  (mirrors what was done for JPM in commit `e173726`).

## Related

- [`docs/admin/research/scrapers/jpm.md`](../research/scrapers/jpm.md) —
  the JPM Phase 2 work that surfaced this.
- Commit `e173726` — adds JPM to both registries (correctly) and
  introduces the `--vendor` flag.
- [`docs/admin/research/onboarding_new_vendor.md`](../research/onboarding_new_vendor.md)
  — Phase 2 references this probe as the canonical listing-API
  discovery tool; broken vendors can't follow the playbook until this
  is fixed.
