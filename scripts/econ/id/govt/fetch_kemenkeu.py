"""Kemenkeu (Ministry of Finance) -- BLOCKED from this network. Not built.

This module deliberately fetches nothing. It exists so the daily pull
reports MoF as a known, named blocker every run instead of the gap being
invisible, and so the next person does not repeat the ~10 probes below.

**What MoF would give us** (it is genuinely Tier 1): APBN KiTa -- the
monthly budget-realisation release -- plus tax-revenue prints, the annual
Budget (Nota Keuangan/RAPBN) and the fiscal-policy communication behind
Indonesia's deficit path.

**Why it is not reachable** (probed 2026-09-21):

1. `www.kemenkeu.go.id` is an Angular SPA. Every route -- `/`,
   `/informasi-publik/publikasi/siaran-pers`, `?page=1` -- returns the
   identical 27,009-byte shell. There is no server-rendered listing to
   parse.
2. The SPA's data API is not discoverable statically. All four JS bundles
   (`main`, `vendor`, `scripts`, `runtime`, ~1.1 MB total) contain ZERO
   `kemenkeu.go.id` API URLs and zero `/api/v{n}` paths -- only
   `media.kemenkeu.go.id/API/GetAsset/...` image endpoints. Guessed
   endpoints (`/feed`, `/rss`, `/rss.xml`, `/wp-json/wp/v2/posts`,
   `/api/...`, `kemenkeu-prime.kemenkeu.go.id/api/...`) all return the
   shell or 404. `sitemap.xml` lists static routes only, no content.
3. The normal way to resolve (2) -- load the page in a browser and watch
   the network tab -- is **blocked by RV's corporate firewall**. Playwright
   headless Chromium gets an interstitial, not the site:

       Web Page Blocked!
       URL: www.kemenkeu.go.id/informasi-publik/publikasi/siaran-pers
       Attack ID: 20000051

   Note this is host-specific and transport-specific: plain httpx DOES
   retrieve the SPA shell from the same machine, and the sibling host
   `djppr.kemenkeu.go.id` is fully reachable (see `fetch_djppr.py`). So it
   is a proxy rule on this host, not a `.kemenkeu.go.id` blanket block and
   not the site rejecting us.

**H.6 gate RESOLVED 2026-09-21: the site loads fine in the user's own
browser.** So this is RV's proxy rule against automated traffic, not the site
rejecting us and not an outage. That fixes the diagnosis and the next step:

  1. Request a corp-firewall allowlist entry for `www.kemenkeu.go.id`
     (the block fires on Chromium/Playwright; plain httpx already passes,
     which is why the SPA shell is reachable). Request text is drafted in
     `docs/admin/econ/indonesia/id_govt_doc_sources.md` section 2.
  2. Once allowed, open the page in DevTools, capture the XHR the SPA makes
     for its press listing, and build a normal JSON fetcher here — per
     [[feedback-devtools-beats-api-probing]], do NOT go back to guessing
     endpoints; steps 1-2 of the probe list above already ruled that out.

Until then this module stays a non-fetcher so the daily report keeps naming
the gap.

**Impact is limited, which is why this is deferred rather than escalated
mid-task.** Track A does not depend on MoF at all: fiscal aggregates come
from BI SEKI IV.1-3 (`bi_fiscal`, 6 indicators) and debt/issuance from
DJPPR, both live. What is missing is the narrative layer -- the APBN KiTa
commentary -- and DJPPR's `siaranpers` carries much of the debt-side story.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _http import make_session
from _models import FetchResult

VENDOR_CODE = "kemenkeu"

SPA_URL = "https://www.kemenkeu.go.id/informasi-publik/publikasi/siaran-pers"

# The shell is this size for every route; seeing it means we got the SPA,
# not a listing. Recorded as evidence, not used as a parsing signal.
SPA_SHELL_BYTES = 27_009

BLOCK_REASON = (
    "MoF is an Angular SPA with no discoverable data API, and the browser "
    "route needed to discover it is blocked by RV's corp firewall "
    "(Attack ID 20000051). Needs user-browser verification -- see module "
    "docstring."
)


def discover(throttle_s: float = 1.0) -> FetchResult:
    """Report the blocker; fetch nothing.

    Still makes one cheap GET so that the day the transport changes, the
    note says so rather than repeating a stale claim.
    """
    note = BLOCK_REASON
    try:
        with make_session(timeout=20.0) as client:
            r = client.get(SPA_URL)
        if len(r.content) != SPA_SHELL_BYTES:
            note = (
                f"SPA shell is {len(r.content):,}B, expected "
                f"{SPA_SHELL_BYTES:,}B -- MoF's front end CHANGED. "
                f"Re-probe for a server-rendered listing or a JSON API; "
                f"this module may now be buildable."
            )
    except Exception as exc:
        note = f"{BLOCK_REASON} (probe also errored: {type(exc).__name__})"

    return FetchResult(
        vendor_code=VENDOR_CODE, ok=False, items=[],
        error="not implemented - transport blocked", note=note,
    )


if __name__ == "__main__":
    res = discover()
    print(f"kemenkeu ok={res.ok} items={len(res.items)}")
    print(f"  {res.note}")
