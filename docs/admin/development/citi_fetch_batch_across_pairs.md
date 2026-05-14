# Follow-up: Batch Citi `fetch_and_parse_batched` calls across pairs

- **Date filed**: 2026-05-15
- **Status**: deferred — perf opportunity, contract-changing
- **Triggered by**: file 8 walk of [`src/imdr/domains/fx/extractors_rate.py`](../../../src/imdr/domains/fx/extractors_rate.py)
- **Scope**: any Citi extractor that loops `fetch_and_parse_batched` per logical group when the per-group tag count is much smaller than `citi_batch_size`.

## Today's behavior — under-batching

`CitiVelocityFXRateExtractor.extract()` ([lines 83-106](../../../src/imdr/domains/fx/extractors_rate.py#L83-L106)) loops once per FX pair:

```python
for ccy1, ccy2 in rate_pairs:
    tags = [spot_tag, *outright_tags, *point_tags]          # ~6 tags / pair
    df = fetch_and_parse_batched(self._client, tags, ...)   # one batched call per pair
```

With the live universe (19 non-BBG-only pairs × 6 tags = ~130 tags) and the
default `citi_batch_size = 50`, each per-pair call holds a single sub-batch
of ~6 tags. We make **19 HTTP round-trips** holding ~6 tags each instead of
**3 round-trips** of 50 each. Every per-pair call also pays the
`citi_rate_limit_sec` sleep between batches even though the batch loop never
actually batches more than once.

Quick sizing of the win (live FX rate daily, 130 tags total):

| Mode | HTTP calls | Tags/call (median) | Rate-limit sleeps |
|---|---:|---:|---:|
| Today — per-pair | 19 | 6 | 18 |
| Proposed — cross-pair | 3 | 50 | 2 |

Same shape applies to:

- `CitiVelocityFXVolExtractor` (per-pair × 90 tags = batched cleanly today, less obvious win — verify when walked).
- `RatesCitiExtractor` per-curve loops.
- `RatesBenchExtractor`, `RatesVolExtractor`, `EquityIndexExtractor`, etc. — anywhere a `for X in group: fetch_and_parse_batched(...)` pattern lives.

## Why it's deferred — error-contract change

Today's per-pair loop gives **per-pair error granularity**: an HTTP 500 on
pair `EUR/USD` is captured as `{"pair": "EUR/USD", "error": "..."}` in
`extractor.errors` and the loop continues with `GBP/USD`. A `TagQuotaExceeded`
on any single pair re-raises and stops the loop.

A single mega-batched fetch returns one long-form DataFrame containing rows
for all successfully-fetched tags, and one consolidated error list keyed by
**tag**, not pair. Mapping a tag back to its owning pair requires re-parsing
`FX.SPOT.{C1}.{C2}.CITI` etc. — the parsers exist
([`citi_fx_rate_tag_to_internal`](../../../src/imdr/domains/fx/rate_translate.py#L24)),
but the consolidated approach changes the public shape of
`extractor.errors` from `[{"pair": ..., "error": ...}]` to something
tag-keyed. Downstream consumers (the [pipeline](../../../src/imdr/domains/fx/pipeline_rate.py),
the [fx_rate_ingest formatter](../../../src/imdr/notifications/formatters/fx_rate_ingest.py),
the [email template](../../../src/imdr/notifications/templates/fx_rate_ingest.html))
all render the pair-keyed list verbatim.

So this is **not a one-file change**. It's a contract change across:

1. `extractors_rate.py` — flatten the loop.
2. `extractors_vol.py` — same change (or decide it's not worth there).
3. `extractors_rate_bbg.py` — different path, not Citi.
4. Rates / equity / commodities Citi extractors — same pattern review.
5. Pipeline post-extract error rendering — pair vs tag.
6. Notification formatters + Jinja templates.
7. Tests for all of the above.

## Proposed shape

A two-pass `extract()` that gathers all tags first, then post-fans-out:

```python
def extract(...) -> pd.DataFrame:
    # 1. Plan: build the full tag list with a pair-back-map.
    all_tags: list[str] = []
    tag_to_pair: dict[str, tuple[str, str]] = {}
    for ccy1, ccy2 in rate_pairs:
        for tag in self._build_pair_tags(ccy1, ccy2):
            all_tags.append(tag)
            tag_to_pair[tag] = (ccy1, ccy2)

    # 2. Pre-flight budget (unchanged — still total tag count).
    if self._quota_tracker is not None:
        self._quota_tracker.check_budget(len(all_tags), "fx.citi_rate")

    # 3. Single batched fetch.
    long_df = fetch_and_parse_batched(
        self._client, all_tags, start, end, frequency,
        self._batch_size, self._rate_limit,
        response_parser=citi_fx_rate_response_to_long_df,
        quota_tracker=self._quota_tracker,
        pipeline_name="fx.citi_rate",
        tag_errors=self.tag_errors,  # already tag-keyed by the helper
    )

    # 4. Post-fan-out: project tag-level errors back to pair-level for
    #    backwards-compatible `self.errors` shape, OR change the contract
    #    explicitly (rename `errors` → `pair_errors` + add `failed_tags`).
    ...

    return pivot_long_to_wide(long_df) if not long_df.empty else pd.DataFrame(columns=WIDE_COLUMNS)
```

## Decision points before this lands

1. **Keep pair-keyed errors or move to tag-keyed?** Pair-keyed preserves the
   current notification/UI shape but requires a tag → pair back-map. Tag-keyed
   is the natural output of `fetch_and_parse_batched` and matches what the
   Citi API already gives us.
2. **What does `TagQuotaExceeded` mid-batch mean?** Today: stop the per-pair
   loop after the offending pair completes. With mega-batches: the helper
   raises mid-fetch with *partial* tag results in `tag_errors`. Pipeline
   needs to accept partial results.
3. **Do we want a `partial` flag on the extracted DataFrame** so the pipeline
   can opt to skip the DB write entirely if the fetch was incomplete?
4. **Test cost:** the existing 11 tests in
   [tests/unit/test_fx_rate_extractor.py](../../../tests/unit/test_fx_rate_extractor.py)
   are pair-loop-oriented — they'd be replaced wholesale.

## When to do this

Bundle with the **healthchecks redesign** + **per-domain trim** work
(repo-review Stages C5 + D1/D2). Touching extractors across all Citi domains
in one pass means the contract change ripples once, not five times.

If a single Citi-rate-limit incident triggers it sooner (e.g. live FX rate
ingest tripping the 15-rps cap because of the 18-sleep cadence), do it on
the FX rate extractor first as a pilot and accept the shape change locally.
