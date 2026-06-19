"""UPAg IMC (Market Intelligence Centre) — Agmarknet mandi prices.

Source: `dash.upag.gov.in/_dash-update-component` — Plotly Dash callback
for the IMC report at `upag.gov.in/dash-reports/imc`. Closes A33 (the
Agmarknet mandi-prices stream, otherwise corp-firewall blocked at
agmarknet.gov.in directly).

Component-prefix `imc-{section}` with 5 sections:
  - cereals    (default commodity: Paddy; also returns Rice, Wheat)
  - pulses     (default: Tur; also Gram, etc.)
  - oilseeds   (default: Rapeseed & Mustard; also Groundnut, Soyabean)
  - topcrops   (default: Onion; also Tomato, Potato)
  - othercrops (placeholder; not probed)

The data callback for `imc-{section}-line-graph1.figure` returns 3
traces (the primary commodity + 2 related) with **8 anchor-date
prices each**:
  3yr ago, 2yr ago, 1yr ago, 1mo ago, 3wks ago, 2wks ago, 1wk ago, today

Prices are Plotly-binary-encoded (`{dtype: "f8", bdata: base64}`) →
decoded to 8 float64s. The 8 obs_dates are parsed from the x-axis
string labels.

Run weekly to accumulate the today-point + refresh anchor structure.
Each run produces ~12 commodities × 8 dates = ~96 observations.

Cell mapping (see docs/admin/econ/india/in_coverage_plan.md):
  Cluster 4 (agriculture) — wholesale mandi prices via Agmarknet feed.
                             Pairs with UPAg MSP (input price) +
                             AIAPY (output volume).
"""
from __future__ import annotations

import base64
import datetime
import re
import struct

import httpx

from imdr.domains.econ.schema import IndicatorRow, ObservationRow
from imdr.domains.econ.upag import fetch_signature, post_callback, slug
from scripts.econ._runner import run_main

UTC = datetime.timezone.utc

# 5 sections; each has a "default" commodity that picks the trace set
# the server returns (it also returns 2 related commodities per call).
_SECTIONS: list[dict] = [
    {"name": "cereals",  "default_commodity": "Paddy"},
    {"name": "pulses",   "default_commodity": "Tur"},
    {"name": "oilseeds", "default_commodity": "Rapeseed & Mustard"},
    {"name": "topcrops", "default_commodity": "Onion"},
]
# `othercrops` skipped — the schema is different (no commodity selector).

# x-axis date parser. Strings look like "Three years ago as on<br>2023-06-08"
# or "Price as on<br>2026-06-08".
_X_DATE_RE = re.compile(r"as on<br>(\d{4}-\d{2}-\d{2})")


def _decode_plotly_f8(field: dict | list) -> list[float]:
    """Decode a Plotly figure value that may be either a plain list or
    a ``{dtype: 'f8', bdata: <base64>}`` binary-encoded array.

    Newer Plotly versions use binary encoding to compress numeric
    arrays. Both UPAg and many other Dash apps will hit us with
    either shape depending on the deployed Plotly version, so handle
    both.
    """
    if isinstance(field, list):
        # Plain list of numbers
        return [float(v) for v in field if isinstance(v, (int, float))]
    if isinstance(field, dict) and field.get("dtype") == "f8":
        raw = base64.b64decode(field["bdata"])
        n = len(raw) // 8
        return list(struct.unpack(f"<{n}d", raw))
    return []


def _build_filters(section: str, commodity: str) -> dict:
    """The full filters dict — IMC requires all 5 sections to be present
    even if only one is being queried."""
    section_template = {
        "date": "", "month": "", "year": "",
        "source": "Agmarknet", "source_data2": "Agmarknet",
        "map_filter": "Mandi Arrival Quantity",
        "filter": "top_3_mandis",
    }
    defaults = {
        "oilseeds": "Rapeseed & Mustard",
        "pulses":   "Tur",
        "cereals":  "Paddy",
        "topcrops": "Onion",
    }
    filters = {
        sec: {**section_template, "commodity":
              (commodity if sec == section else defaults.get(sec, ""))}
        for sec in defaults
    }
    filters["othercrops"] = {"date": ""}
    return filters


def _fetch_section(
    client: httpx.Client, section: str, commodity: str,
    sig=None,
) -> list[dict]:
    """Hit the data callback for one section; return the list of
    line-graph1 traces (each trace = one commodity in the section).

    Pass ``sig`` (a `CallbackSignature`) to skip the per-call
    `_dash-dependencies` GET — only useful if all sections share
    the same output signature, which they do NOT (each section has
    a section-prefixed output). Kept as a parameter for the future
    case where we cache per-section signatures.
    """
    if sig is None:
        sig = fetch_signature(
            client,
            output_contains=f"imc-{section}-line-graph1.figure",
        )
    resp = post_callback(
        client, sig,
        inputs=[
            {"id": "imc-header-tabs", "property": "value",
             "value": f"imc-{section}-tab"},
            {"id": f"imc-{section}-body-tab", "property": "value",
             "value": "line1"},
            {"id": "imc-filters-store", "property": "data",
             "value": _build_filters(section, commodity)},
        ],
        state=[{"id": "url", "property": "search",
                "value": "?rtype=dashboard"}],
        changed_prop_ids=["imc-filters-store.data"],
    )
    fig = (resp.get(f"imc-{section}-line-graph1") or {}).get("figure", {})
    return fig.get("data", []) or []


def run_fetch(
    since: str | None,
    until: str | None,
) -> tuple[list[IndicatorRow], list[ObservationRow]]:
    since_dt = datetime.date.fromisoformat(since) if since else None
    until_dt = datetime.date.fromisoformat(until) if until else None
    now = datetime.datetime.now(UTC)

    indicators: dict[str, IndicatorRow] = {}
    observations: list[ObservationRow] = []
    seen_obs: set[tuple[str, datetime.date]] = set()

    with httpx.Client(timeout=60, follow_redirects=True) as c:
        # Cache per-section callback signatures up-front so the data
        # callback round-trip per section is just the data POST (no
        # `_dash-dependencies` re-fetch). Each section has its own
        # output prefix so signatures don't reuse across sections.
        sigs = {}
        for section in _SECTIONS:
            sec_name = section["name"]
            try:
                sigs[sec_name] = fetch_signature(
                    c, output_contains=f"imc-{sec_name}-line-graph1.figure",
                )
            except Exception as e:
                print(f"  section {sec_name!r} sig fetch failed: {e}")
                sigs[sec_name] = None

        for section in _SECTIONS:
            sec_name = section["name"]
            print(f"  section {sec_name!r} (primary={section['default_commodity']!r})")
            if sigs.get(sec_name) is None:
                continue
            try:
                traces = _fetch_section(c, sec_name, section["default_commodity"],
                                         sig=sigs[sec_name])
            except Exception as e:
                print(f"    FAIL {type(e).__name__}: {str(e)[:80]}")
                continue
            print(f"    {len(traces)} traces")

            for tr in traces:
                commodity = (tr.get("name") or "").strip()
                if not commodity:
                    continue
                x_labels = tr.get("x") or []
                y_values = _decode_plotly_f8(tr.get("y"))
                if not x_labels or len(y_values) != len(x_labels):
                    print(f"      skip {commodity!r}: x/y mismatch ({len(x_labels)}/{len(y_values)})")
                    continue

                comm_slug = slug(commodity)
                sec_slug = slug(sec_name)
                imdr_code = f"INDIA.MANDI.AGMARKNET.{sec_slug}.{comm_slug}.INR_QTL.IN"
                if imdr_code not in indicators:
                    indicators[imdr_code] = IndicatorRow(
                        imdr_code=imdr_code, vendor_name="UPAg",
                        source_code=f"UPAg/IMC/{sec_slug}/{comm_slug}/Agmarknet",
                        display_name=(
                            f"India mandi price — {commodity} ({sec_name}, "
                            f"Agmarknet top-3 mandis, INR/Qtl)"
                        )[:255],
                        unit="inr", frequency="WEEKLY", country_iso="IN",
                        category="other",
                        is_seasonally_adjusted=False, bbg_ticker=None,
                    )
                for label, value in zip(x_labels, y_values):
                    if not isinstance(value, (int, float)) or value <= 0:
                        continue
                    m = _X_DATE_RE.search(str(label))
                    if not m:
                        continue
                    try:
                        obs_date = datetime.date.fromisoformat(m.group(1))
                    except ValueError:
                        continue
                    if since_dt and obs_date < since_dt:
                        continue
                    if until_dt and obs_date > until_dt:
                        continue
                    key = (imdr_code, obs_date)
                    if key in seen_obs:
                        continue
                    seen_obs.add(key)
                    observations.append(ObservationRow(
                        imdr_code=imdr_code, obs_date=obs_date, vintage=0,
                        release_date=now, value=float(value), ingested_at=now,
                    ))
                print(f"      {commodity}: {len(x_labels)} anchors emitted")
    return list(indicators.values()), observations


def main() -> int:
    return run_main(vendor="upag", topic="imc",
                    fetch_fn=run_fetch,
                    description=__doc__.splitlines()[0] if __doc__ else "",
                    country_code="IN")


if __name__ == "__main__":
    import sys
    sys.exit(main())
