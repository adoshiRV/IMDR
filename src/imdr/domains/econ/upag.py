"""UPAg (Unified Portal for Agricultural Statistics) Plotly Dash callback helper.

`dash.upag.gov.in` exposes 92+ Plotly Dash reports under a single
`_dash-update-component` callback endpoint. The shared protocol:

1. ``GET /_dash-dependencies`` returns the full callback graph (805
   callbacks as of 2026-06-11). Each callback declares ``output``
   (dotted-string id.property list), ``inputs``, ``state``.
2. ``POST /_dash-update-component`` with ``{output, outputs, inputs,
   changedPropIds, state}`` returns ``{response: {<id>: {<property>:
   <value>}}}`` for each output.

Fetchers in this project mostly target the **data store** callback for
a report — one whose output includes ``<prefix>-idstore.data`` or
``<prefix>-store.data`` — because that holds the unrendered tabular
data list. From there it's a flat record map: ``Crop / Year / Value /
…``.

This module centralises the things every UPAg fetcher needs:
  - the URL constants + browser-like headers
  - a fresh-signature reader for the target callback (resilient to
    UPAg adding/removing output slots over time)
  - a single ``post_callback`` helper
  - a stable ``slug()`` for ``imdr_code`` stems

UPAg is the corp-firewall-reachable replacement for agricoop.gov.in /
cacp.dacnet.nic.in / farmer.gov.in (all DNS-blocked from rvsg-fs01).
Reports decoded:
  - mip-msp-data2  → Commodity-wise MSP (A31)         ✅ live fetcher
  - aiapy          → All-India APY (A26)              ✅ live fetcher
  - pcas / cwwg    → Progressive sowing / weather     scoped, deferred
  - imc-{section}  → Market Intelligence mandi prices scoped, deferred
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

import httpx


DASH_BASE = "https://dash.upag.gov.in"
URL_UPDATE = f"{DASH_BASE}/_dash-update-component"
URL_DEPS = f"{DASH_BASE}/_dash-dependencies"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 Chrome/120 Safari/537.36"
    ),
    "Referer": "https://upag.gov.in/",
    "Content-Type": "application/json",
    "Accept": "application/json",
}


@dataclass(frozen=True)
class CallbackSignature:
    """Decoded ``output`` string of a Dash callback.

    The Dash protocol encodes outputs as a flat dotted string like
    ``..a-idstore.data...a-suffix-title.children..``. Parsing it into a
    structured ``outputs`` list keeps fetchers resilient if UPAg adds
    or reorders output slots.
    """
    output: str
    outputs: list[dict]


def _parse_output_string(out: str) -> list[dict]:
    parts = re.findall(r"(?<=\.\.)([^.]+)\.([^.]+)(?=\.\.)", out)
    return [{"id": i, "property": p} for i, p in parts]


def fetch_signature(
    client: httpx.Client, *, output_contains: str, exclude_contains: str | None = None,
) -> CallbackSignature:
    """Locate the live callback signature by substring match.

    ``output_contains`` must appear in the target callback's ``output``
    string; ``exclude_contains`` skips matches that contain it (useful
    for distinguishing ``aiapy-idstore`` from ``aiapy-idstore-yw``).
    """
    r = client.get(URL_DEPS, headers={"User-Agent": HEADERS["User-Agent"],
                                       "Referer": HEADERS["Referer"]},
                    timeout=30)
    r.raise_for_status()
    deps = r.json()
    for cb in deps:
        out = cb.get("output", "")
        if output_contains not in out:
            continue
        if exclude_contains and exclude_contains in out:
            continue
        return CallbackSignature(output=out, outputs=_parse_output_string(out))
    raise RuntimeError(
        f"UPAg callback signature with {output_contains!r} not found in _dash-dependencies"
    )


def post_callback(
    client: httpx.Client,
    sig: CallbackSignature,
    *,
    inputs: list[dict],
    state: list[dict] | None = None,
    changed_prop_ids: list[str] | None = None,
) -> dict:
    """POST the ``_dash-update-component`` callback; return ``response``.

    ``inputs`` is the Dash standard list of ``{id, property, value}``
    dicts. Caller picks values they want from the returned response
    dict (keyed by output id).
    """
    body = {
        "output": sig.output,
        "outputs": sig.outputs,
        "inputs": inputs,
        "changedPropIds": changed_prop_ids or [inp["id"] + "." + inp["property"]
                                                for inp in inputs],
        "state": state or [],
    }
    r = client.post(URL_UPDATE, headers=HEADERS, json=body, timeout=60)
    r.raise_for_status()
    return r.json().get("response", {}) or {}


_SLUG_MAXLEN = 40


def slug(s: str, *, maxlen: int = _SLUG_MAXLEN) -> str:
    """Stable code-safe slug for an ``imdr_code`` stem.

    All-uppercase, alphanumeric + underscore, capped at ``maxlen`` chars
    (default 40 — sized to fit the longest India food-basket commodity name).
    Consistent across all UPAg + food-nowcast fetchers so the same crop in
    two reports produces the same slug — prevents accidental code splits.
    """
    out = re.sub(r"[^A-Za-z0-9]+", "_", s).strip("_").upper()
    return out[:maxlen] or "X"
