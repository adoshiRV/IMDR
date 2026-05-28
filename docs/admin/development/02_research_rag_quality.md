# 02 — Research RAG quality: findings & production checklist

- **Date filed**: 2026-05-22
- **Status**: open — actively being worked. Phase 1 (measurement) not started; some Phase 2 pre-requisites already in place (see §A).
- **Triggered by**: 21-May intra-day audit. Corpus reached 207 reports across 6 vendors, retrieval quality is now the bottleneck, not coverage.
- **Scope note**: this doc tracks **retrieval/generation quality** for the research RAG system. Pipeline-throughput / dedup work is filed separately in [`research_reports_intraday_ingest_optimization.md`](research_reports_intraday_ingest_optimization.md).

> Cross-refs:
> - System overview: [`docs/admin/research/index.md`](../research/index.md)
> - Vector store: [`docs/admin/research/qdrant.md`](../research/qdrant.md)
> - Retrieval concepts (the *why*): [`docs/admin/research/retrieval_concepts.md`](../research/retrieval_concepts.md)
> - Embedding model reference: [`playground/research/EMBEDDING_MODELS.md`](../../../playground/research/EMBEDDING_MODELS.md)

---

## A. Current IMDR state (what already exists)

Pulled from the codebase 2026-05-22 so this doc doesn't propose work that's done:

| Capability | Status | Where |
|---|---|---|
| Qdrant local server | live | `127.0.0.1:6333`, Windows Service. See [`docs/admin/qdrant/`](../qdrant/index.md) |
| Active collection | live | `research_gemini_embedding_2_3072d`, 3072-dim cosine |
| Payload indexes (`vendor_code`, `publish_date`, `report_id`) | **live** | `src/imdr/connectors/qdrant_schema.py:64-68` — created on every new collection |
| Provider-aware query embedding (Voyage vs Gemini framing) | live | `playground/research/retrieve.py` |
| Score floor (`--min-score`, default 0.45) | live | `retrieve.py` — empirically tuned on 81-chunk corpus |
| Group-by-report (collapse multi-chunk hits) | live | `retrieve.py --group-by-report` |
| Metadata filters (`--vendor`, `--report`, `--since`) | live | `retrieve.py:_build_filters()` |
| Watermark-stripped content hash (idempotency) | live | `parse._normalise_for_hash()` |
| Multi-model coexistence in same DB (UNIQUE on `chunk_id, model_id`) | live | migration 033 + `dim_embedding_model` |
| Voyage 3-large / finance-2 / gemini-001 wired in code | yes, **no live collection** | `playground/research/ingest/embed.py` |
| MCP server (`imdr-research`) | live, owner-only | `mcp/research_server.py` |
| Relevance filter (drops single-name equity by default) | live | `ingest/relevance.py`, settings flag |
| BM25 / sparse vectors | **not started** | — |
| Cross-encoder rerank | **not started** | — |
| ColBERT late-interaction | **not started** | — |
| Eval set (golden queries) | **not started** | placeholder dir suggested: `playground/research/eval/` |
| Scalar quantization | not needed yet | corpus < 500K chunks |
| `market_tag` / `theme_tag` payload indexes | **not created** | classifier writes these to MSSQL but they're not promoted to Qdrant payload |

**Observed daily volume (24h, 2026-05-21)**: 911 discovered post-filter, 339 kept after relevance filter. Vendors: ANZ 18, Barclays 93, Goldman 136, HSBC 11, MS 15, Nomura 66. ([`docs/admin/research/index.md`](../research/index.md))

**Current corpus**: 207 reports total. Today (21-May): 46 reports — Nomura 28, HSBC 12, ANZ 6. **GS / MS / Barclays gap since 14-May** — pipeline issue to investigate (likely the auth / session expiry pattern, not retrieval).

---

## B. Architecture (read & write paths)

```
WRITE PATH
──────────────────────────────────────────────────────
Vendor email / PDF
    → ETL parser (chunk + summarise)
        → IMDR SQL (research.dim_report, full text + metadata)
        → Gemini embedding-2 (per chunk → 3072-dim vector)
            → Qdrant (vector store)

READ PATH
──────────────────────────────────────────────────────
Claude (query text)
    → Gemini embedding-2 (embed query → vector)   ← quota bottleneck (see C.1)
        → Qdrant ANN search (cosine similarity, in-graph filter)
            → top-K chunks → Claude (synthesis)
```

The generation model (Claude) is fully decoupled from the embedding model — only the embedding side has to be consistent between index and query. This is a property to preserve, not a flaw to fix.

---

## C. Known issues

### C.1 Gemini RPM quota (429 at query time)

- **Error**: `Quota exceeded for aiplatform.googleapis.com/global_embed_content_requests_per_minute_per_base_model`
- **Cause**: per-minute rate limit on the Gemini API key for query-time embedding
- **Fix**: raise RPM via Google AI Studio / GCP console
- Not a design problem — the key just needs a higher tier.

### C.2 GS / MS / Barclays ingestion gap (no reports since 14-May)

Nomura / HSBC / ANZ are current; the other three are stale. Likely scraper-side (auth, session, or listing-API rotation) rather than RAG-side, but worth confirming before doing any quality work — there's no point tuning retrieval against a corpus that's missing the last week of three vendors.

**Action**: re-run `python playground/research/dry_test_all_vendors.py` and inspect `playground/research/_backfill_log_*.txt`. Filed as the first item in Phase 1 because measurement on a stale corpus is misleading.

---

## D. Why Gemini embedding-2 is the default

(Mirrors [`EMBEDDING_MODELS.md`](../../../playground/research/EMBEDDING_MODELS.md) — repeated here so this doc is self-contained.)

- Research PDFs are **multimodal** — yield curve charts, vol-surface heatmaps, tables embedded as images. Gemini handles text+image+PDF in a unified 3072-dim space.
- Voyage Finance-2 and other text-only models miss image-embedded content entirely.
- Strong cross-lingual scores (relevant for Asia EM reports with CJK / Bahasa snippets).
- Auto-renormalised under Matryoshka truncation — we use full 3072 today, but can compress without manual L2 normalisation later.
- Generation model is decoupled — not locked to Gemini for synthesis.

`voyage-finance-2` is wired in code (`ingest/embed.py`) as a future A/B candidate. To activate, add a `CollectionSpec` to `src/imdr/connectors/qdrant_schema.py:80` and run `python -m imdr.connectors.qdrant_schema apply`. Multi-model coexistence is already designed in (UNIQUE on `chunk_id, model_id`).

---

## E. Evaluation framework

### E.1 Three layers to measure

| Layer | What it tests |
|---|---|
| Retrieval | Does Qdrant return the right chunks? |
| Generation | Does Claude use the chunks faithfully? |
| End-to-end | Is the final answer correct and grounded? |

### E.2 Metric weights (IMDR-specific)

| Metric | Weight | Rationale |
|---|---|---|
| Context precision | 0.95 | Cross-vendor noise is the main risk — irrelevant chunks corrupt synthesis |
| Faithfulness | 0.95 | Trading desk — hallucinated macro views are an active risk |
| Recall@K | 0.80 | Cross-vendor coverage matters — if 3 banks wrote on USD weakness, want all 3 |
| nDCG@10 | 0.75 | Claude reads top-K in order — best chunks should rank first |
| Diversity / redundancy | 0.78 | Nomura publishes ~28 reports/day — without diversity, top-10 could all be Nomura |
| Multimodal recall | 0.90 | Core reason for Gemini — charts and vol surfaces must be retrievable |
| Domain vocabulary fit | 0.85 | Gemini may blur "cross-currency basis", "SOFR OIS 2Y" — addressed by BM25 |
| Hybrid retrieval (BM25) | 0.85 | ~27% recall improvement for exact financial terms |
| Cross-lingual | 0.55 | Relevant but secondary |
| MRR | 0.45 | Less critical for synthesis — all top-K passed to Claude anyway |
| Long-doc context | 0.50 | We chunk before embedding, so 32K window matters less |
| Matryoshka compression | 0.30 | Not yet relevant at current corpus size |
| MTEB leaderboard | 0.25 | Directional only — documented domain mismatch for financial text |

### E.3 Production thresholds

- Context precision > 0.80
- Faithfulness > 0.80
- Answer relevancy > 0.75

### E.4 Tooling by phase

| Phase | Tool | Purpose |
|---|---|---|
| Exploration | RAGAS | Standard metrics, low setup — use first |
| CI/CD gates | DeepEval | Pass/fail on every pipeline / model change |
| Dashboards | TruLens | Experiment comparison across configurations |
| Observability | Arize Phoenix | Visual debugging of retrieval failures |

**Note**: RAGAS can produce NaN scores when the LLM judge returns invalid JSON. Pin version and wrap eval calls in try/except in CI.

---

## F. Domain vocabulary gap — the core risk

Gemini is general-purpose. Terms like `USDKRW NDF 1M implied yield`, `cross-currency basis`, `swaption skew 25d`, `SOFR OIS 2Y` get mapped into imprecise vector neighbourhoods — semantic blurring across related-but-distinct concepts.

### What does NOT fix this

- Pre-seeding Qdrant with finance vocabulary terms — adds noise, doesn't sharpen the space.
- The underlying embedding model maps terms the same way regardless of what else is in the DB.

### What does fix this (ordered by effort)

1. **BM25 hybrid layer** — quick win, no re-embedding. Qdrant 1.10+ supports sparse vectors natively. Literature: ~27% recall improvement on exact financial terms.
2. **Query expansion via Claude** — cheap, helps general queries. "USD weakness" → "USD weakness DXY dollar index greenback decline".
3. **Fine-tuning the embedding model** — proper fix, needs ~500–2000 labelled query-chunk pairs. arxiv 2512.08088 reports 27.7% MRR / 44.6% DCG improvement on financial filings.

---

## G. Fine-tuning — when & hyperparameters

### When it's worth it

- After BM25 hybrid is in place and a baseline eval score exists.
- When domain-vocabulary recall is measurably poor on the golden set.
- When corpus is large enough for ~500+ labelled pairs.

### Training

- Method: contrastive fine-tuning with hard-negative mining.
- Framework: `sentence-transformers` over any base model.
- Loss: `MultipleNegativesRankingLoss` (or `CachedMultipleNegativesRankingLoss` for large batches).

### Hyperparameters

| Parameter | Starting value | Notes |
|---|---|---|
| Optimizer | AdamW | With linear warmup |
| Learning rate | 2e-5 | Most critical — too high destroys pre-trained representations |
| Warmup steps | 10% of total | Prevents early instability |
| Batch size | 64–256 | Larger = better contrastive signal |
| Epochs | 3–5 | Monitor for overfitting on domain terms |
| Hard-negative ratio | 1:1 to 1:3 | Positives to hard negatives per query |

### Evaluation after fine-tuning

- Compare faithfulness before/after — fine-tuned models can override retrieved context with memorised stale information.
- Always compare against the base model on the same golden set.
- Consider Matryoshka 256-dim reduction after fine-tuning if storage is a concern (Gemini supports it natively).

---

## H. Production implementation order

```
Phase 1 — Measurement (before changing anything)
─────────────────────────────────────────────────
[ ] Investigate GS / MS / Barclays ingestion gap (no reports since 14-May)
[ ] Raise RPM quota on Gemini API key (C.1)
[ ] Build golden test set: 50–100 queries under playground/research/eval/
    queries.yml + run_eval.py + reports/ (layout already proposed in
    retrieval_concepts.md §"Build an evaluation set first")
[ ] Run RAGAS baseline: context precision, faithfulness, recall@K
[ ] Store baseline scores — everything else measured against these

Phase 2 — Quick wins (no re-embedding)
─────────────────────────────────────────────────
[ ] Promote market_tag + theme_tag to Qdrant payload + index them in
    qdrant_schema.CollectionSpec.payload_indexes
[ ] Add sparse BM25 vector type to CollectionSpec; back-index existing
    ~5K chunks (re-index, NOT re-embed)
[ ] Switch retrieve.py to FusionQuery(fusion=Fusion.RRF) prefetch
[ ] Implement query expansion step via Claude before embedding
[ ] Add diversity / MMR reranking (top-10 selection from top-100) to
    prevent Nomura-dominated results
[ ] Re-run RAGAS — measure delta vs baseline

Phase 3 — CI/CD (production hardening)
─────────────────────────────────────────────────
[ ] Wire DeepEval into the regression suite; thresholds on
    faithfulness ≥ 0.80, context precision ≥ 0.80
[ ] Trigger full eval on any embedding-model or chunking change

Phase 4 — Fine-tuning (only after Phase 1–2 complete)
─────────────────────────────────────────────────
[ ] Generate labelled training pairs from corpus (Claude can help)
[ ] Hard-negative mining pass using current model
[ ] Fine-tune base model with sentence-transformers
[ ] Re-embed full corpus → new CollectionSpec (multi-model design
    means we can A/B against gemini-embedding-2 in place)
[ ] Re-run full golden test set
```

---

## I. Qdrant optimization

### I.1 HNSW — the core knobs

| Parameter | Where set | Effect |
|---|---|---|
| `m` | Collection creation | Edges per node. Higher = better recall, more memory, slower build. Default 16. |
| `ef_construct` | Collection creation | Neighbours considered during build. Default 100. |
| `hnsw_ef` | Per query | Neighbours evaluated at search time. Main runtime dial. |

At current corpus (~5K chunks) defaults are noise; HNSW tuning matters once a collection crosses ~100K. `hnsw_ef` is the lever to raise for "what did all vendors say about X this week" cross-vendor synthesis queries.

### I.2 Hybrid search — BM25 + dense in one query

Qdrant 1.10+ supports sparse vectors natively. Fusion via **RRF (Reciprocal Rank Fusion)** — never linear combination (score scales are incomparable).

Collection setup (requires re-index, no re-embedding):

```python
vectors_config = {
    "gemini": VectorParams(size=3072, distance=Distance.COSINE),
    "bm25":   SparseVectorParams()
}
```

Query:

```python
client.query_points(
    collection_name="research_gemini_embedding_2_3072d",
    prefetch=[
        Prefetch(query=dense_vector,  using="gemini", limit=20),
        Prefetch(query=sparse_vector, using="bm25",   limit=20),
    ],
    query=FusionQuery(fusion=Fusion.RRF),
    limit=10
)
```

Wiring location for IMDR: extend `CollectionSpec` in
[`src/imdr/connectors/qdrant_schema.py`](../../../src/imdr/connectors/qdrant_schema.py) to allow a sparse vector type, then rebuild the collection (the multi-model layout already isolates this by collection).

### I.3 Payload indexes & filtered search

Already in place for `vendor_code`, `publish_date`, `report_id`. Filterable HNSW runs filters **inside** the graph traversal, so filtering doesn't degrade recall.

**To add next**: `market_tag`, `theme_tag` — already written into MSSQL by the classifier but not yet promoted to Qdrant payload.

```python
client.create_payload_index("research_gemini_embedding_2_3072d", "market_tag",
                            PayloadSchemaType.KEYWORD)
client.create_payload_index("research_gemini_embedding_2_3072d", "theme_tag",
                            PayloadSchemaType.KEYWORD)
```

Then `retrieve.py --market USDKRW` and similar work natively.

### I.4 Quantization

| Method | Compression | Speed | Loss | When for IMDR |
|---|---|---|---|---|
| Scalar (float32 → int8) | 4x | Moderate | <1% | Once corpus > 500K chunks |
| Binary (float32 → 1-bit) | 32x | Up to 40x | Significant | Not yet — unreliable at 3072 dims w/o rescoring |

```python
quantization_config = ScalarQuantization(
    scalar=ScalarQuantizationConfig(
        type=ScalarType.INT8,
        quantile=0.99,
        always_ram=True,
    )
)
```

At 3072 dims each Gemini vector is ~12 KB; scalar quantization brings it to ~3 KB. Plan but don't apply yet.

### I.5 ColBERT / late interaction (Phase 4+)

```
dense (Gemini) + sparse (BM25)
    → top-100 candidates via RRF
        → ColBERT late interaction reranker
            → top-10 to Claude
```

ColBERT stores one embedding per token. Final score from query-token × doc-token interactions. **Disable HNSW for the ColBERT vector type** — rescoring doesn't use the graph:

```python
"colbert": VectorParams(
    size=128,
    distance=Distance.COSINE,
    multivector_config=MultiVectorConfig(comparator=MultiVectorComparator.MAX_SIM),
    hnsw_config=HnswConfigDiff(m=0)
)
```

Do not add before hybrid + payload indexes are validated against baseline eval scores.

### I.6 Priority order

```
Phase 1 — Zero rebuild
[x] Payload indexes: vendor_code, publish_date, report_id (already live)
[ ] Add market_tag, theme_tag payload indexes
[ ] Validate filtered queries against IMDR SQL metadata

Phase 2 — Re-index (no re-embedding)
[ ] Add sparse BM25 to CollectionSpec; re-index existing chunks
[ ] Switch retrieve.py to hybrid RRF fusion
[ ] Measure recall@K delta vs dense-only baseline

Phase 3 — Memory optimisation
[ ] Scalar quantization (int8) once corpus > 500K chunks
[ ] Tune hnsw_ef per query type using golden set

Phase 4 — Reranking
[ ] Add ColBERT vector type (m=0)
[ ] Update query pipeline: prefetch top-100, rerank to top-10
[ ] Measure faithfulness + precision delta
```

---

## J. Fallacies & pitfalls

> The defining trait of a failed production RAG system is that nothing crashes. The pipeline keeps serving answers, dashboards show healthy latency, eval scores stay pinned to the wiki. Underneath, the system is quietly degrading. — DigitalApplied audit finding, May 2026

Industry analysis in 2026 consistently shows that when RAG fails, the failure point is retrieval **73% of the time**, not generation. The fallacies below are discipline failures, not model upgrades.

### J.1 "Vector search is enough"

Pure dense search returns documents that are *semantically similar* but miss the document that explicitly names the standard / instrument. For IMDR: `USDKRW NDF 1M implied yield`, `RBA 25bp November meeting` are exact-identifier queries. Without BM25 you miss the chunk that contains the exact instrument or event — usually the most critical one.

### J.2 "Chunk size doesn't matter"

Default 1500–2000 token chunks dilute the retrieval signal. Half of all audits find the highest-impact fix is moving from 1500 to 600/50.

**Current IMDR setting** (`playground/research/ingest/chunk.py`): **800 tokens / 100 overlap**, cl100k, page-aware. Reasonable starting point. Diagnostic: pick 15 queries from logs, count what % of sentences in the top retrieved chunk are actually relevant. Below 25% → chunks are too big. Target 40–60%.

For IMDR PDFs (mixed content):

| Content type | Chunk size | Notes |
|---|---|---|
| Narrative prose (macro commentary) | 500–800 tokens | 50-token overlap |
| Data tables | 1 row per chunk | Inject column headers into every chunk |
| Chart captions / figure text | 200–300 tokens | Keep figure reference in payload |
| Executive summaries | 300–500 tokens | Often the highest-signal section |

### J.3 "k=3 is fine"

k=3 is a tutorial default. Multi-hop and synthesis queries need 12–20 candidates with rerank truncation.

For IMDR: "what are all vendors saying about USD this week" is a synthesis query across ~46 daily reports. k=3 returns 3 Nomura chunks. k=20 with rerank returns a cross-vendor picture.

| Query type | k (retrieval) | k (to Claude) |
|---|---|---|
| Single vendor, single topic | 5 | 5 |
| Cross-vendor synthesis | 20 | 10 (after rerank) |
| Specific instrument / event lookup | 10 | 5 |

### J.4 "Lost in the middle"

Documented architectural bias: LLMs show U-shaped performance over long context. Accuracy is highest at the start and end of input; it drops >30% in the middle. RoPE positional encoding has a long-term decay that prioritises start/end tokens.

For IMDR: if you pass 10 chunks in rank order, ranks 4–7 are in the attention dead zone.

**Fix — context ordering**: place highest-confidence chunks at start and end. For 5 chunks, arrange as `[rank 1, rank 4, rank 5, rank 3, rank 2]`. One-line change in context assembly; no model changes.

### J.5 "Eval once at launch"

Embedding-model generations shift every 6–12 months; corpora drift continuously. A v1 RAG that passed audit on launch can quietly lose 10–20 points of retrieval quality in a year with zero code changes.

For IMDR: corpus grows ~40–50 reports/day. Suggested cadence: weekly automated RAGAS run, full manual re-label of golden set quarterly.

### J.6 "Retrieval score = answer quality"

The signal to monitor is **answer refusal rate** and **citation failure rate**, segmented by query type — not raw retrieval score.

For IMDR: a general FX chunk has high cosine similarity to a USDKRW NDF query. Retrieval score looks healthy. The chunk is wrong. The answer hallucinates NDF-specific details from general FX content.

Track citation failure rate separately: if Claude says "according to Goldman..." and no Goldman chunk was retrieved — that's a citation failure, not a retrieval success.

### J.7 "More context = better answer"

Retrieving 10 chunks when 2 are relevant produces context-window pollution — the LLM averages across all of it. Conflicting context is worse: if GS says "Fed on hold through Q3" and Nomura says "Fed cut in July", passing both without metadata produces a silent preference or a blended non-answer.

**Fix**: minimum similarity threshold before a chunk enters context (we have `--min-score 0.45` in `retrieve.py` — this is correct). Tag chunks with `vendor_code` + `publish_date` **in the prompt** so Claude can reason about conflicts explicitly.

### J.8 "MTEB score = our recall"

On a legal contract retrieval system, the top-3 MTEB models ranked 5th/7th/2nd on the in-domain eval. The winner was ranked 11th. Finance has the same documented mismatch.

The only number that matters is **recall@K on your own golden test set, on your own corpus, on your own query distribution**.

### J.9 Severity ranking

| # | Fallacy | Severity | Fix effort | IMDR status |
|---|---|---|---|---|
| J.4 | Lost in the middle | Critical | Low — one-line context reorder | not done |
| J.1 | Vector search is enough | Critical | Medium — BM25 hybrid | not done |
| J.2 | Chunk size doesn't matter | Critical | High — re-chunk corpus | 800/100 — likely OK, validate |
| J.3 | k=3 is fine | High | Low — change a number | `retrieve.py --k` defaults TBD |
| J.6 | Retrieval score = answer quality | High | Medium — add citation tracking | not done |
| J.7 | More context = better | High | Low — add similarity threshold | **done** (`--min-score 0.45`) |
| J.5 | Eval once at launch | Medium | Medium — schedule automation | not done |
| J.8 | MTEB = our recall | Low | None — just stop trusting it | reflected in `EMBEDDING_MODELS.md` |

---

## K. References

- arxiv 2504.06293 — RiskEmbed: financial risk RAG embedding fine-tuning
- arxiv 2503.15191 — Optimising retrieval for financial QA documents
- arxiv 2512.08088 — Embedding adaptation for financial filings via LLM distillation (27.7% MRR, 44.6% DCG)
- tensoria.fr/en/blog/embedding-models-2026-guide — MTEB traps and fine-tuning recipe
- RAGAS: github.com/explodinggradients/ragas
- DeepEval: github.com/confident-ai/deepeval
- Internal: [`docs/admin/research/retrieval_concepts.md`](../research/retrieval_concepts.md) covers HNSW, hybrid fusion, rerank, and tuning methodology in detail.
