# Retrieval — concepts and production architecture

Background reading for the research-RAG retrieval layer. Captures the
*why* behind the choices: HNSW over flat search, Qdrant over alternatives,
hybrid + rerank over pure dense. Read this before tuning parameters in
`retrieve.py` or designing new retrieval flows.

For the system layout (storage location, FK convention, runner
integration) see [qdrant.md](qdrant.md). For the end-to-end pipeline see
[index.md](index.md).

## What retrieval actually is

Retrieval is the answer to: *given a query, find the K most relevant
items from N stored items, where N is large and "relevant" means
semantically close in embedding space.* Embeddings put you in a vector
space; retrieval is fast nearest-neighbor search in that space.

## The similarity metric

Most modern embedding models produce L2-normalized vectors, so inner
product equals cosine similarity:

```
sim(q, d) = (q · d) / (‖q‖ ‖d‖)
```

For normalized vectors this collapses to `q · d`. Euclidean distance is
sometimes used but cosine/dot dominates for embeddings — what you care
about is angular alignment, not magnitude.

IMDR's collections all use cosine distance (see `QdrantWriter.upsert_chunks`
in [`qdrant_writer.py`](../../../playground/research/ingest/qdrant_writer.py)).

## Why brute force fails

Naive search is O(N · d) per query. For N = 100M, d = 1024, that's
~10¹¹ FLOPs per query. SIMD or not, doesn't scale. Approximate
Nearest Neighbor (ANN) algorithms trade a small amount of recall for
sub-linear query time. The metric you care about is **recall@K** —
fraction of true top-K neighbors retrieved by the approximate method.
Production targets 0.95–0.99 recall@10 at millisecond latency.

## HNSW — the dominant algorithm

Hierarchical Navigable Small World is what Qdrant, Weaviate, pgvector,
and (as one option) Milvus actually run. Worth understanding properly
because the parameters bleed into your tuning.

**Build.** Each vector is a node in a multi-layer graph. Layer 0
contains every node; each higher layer contains a logarithmically-
decreasing random subset. Within each layer, every node connects to
its M nearest neighbors. Top layers are sparse with long-range edges,
bottom layer is dense with local edges. The result is a small-world
graph: short average path length, high local clustering — same
Watts-Strogatz property that makes social networks navigable.

**Query.** Enter at the top-layer entry point. Greedy descent — at
each layer, hop to whichever neighbor is closer to q. When no neighbor
is closer, drop a layer. At layer 0, do a wider search bounded by
`ef_search`. Big jumps at the top to find the right neighborhood,
fine-grained search at the bottom.

Two key parameters control the trade-off:

| Parameter | Typical | Effect |
|---|---|---|
| `M` (graph connectivity) | 16 | higher → better recall, more memory |
| `ef_search` (query-time search width) | 64–256 | higher → better recall, slower |

You tune these against a recall@K target on a held-out set. Time
complexity is O(log N) per query, which is the entire reason this
works at scale.

## Other index families, briefly

* **IVF (Inverted File).** k-means partition vectors into ~√N clusters;
  at query, search only the few clusters nearest the query's centroid.
  Lower recall than HNSW but cheaper to build and update.
* **PQ (Product Quantization).** Split each d-dim vector into m
  sub-vectors, quantize each sub-space independently with 256
  centroids per sub-vector (8 bits each). A 1024-dim float32 vector
  (4 KB) compresses to ~16–32 bytes; distances computed via lookup
  tables. Massive memory savings at recall cost — usually combined
  with IVF as IVF-PQ.
* **DiskANN/Vamana.** HNSW-style graph engineered to live on SSD, with
  bounded disk I/O per query. Scales to billions on commodity hardware.

## Filtering is the hard part nobody talks about

You almost never want pure ANN — you want *"chunks where source =
primary AND date > 2026-01-01 AND theme IN (inflation, energy)."*
Three approaches:

1. **Pre-filter** (filter, then ANN over survivors): breaks HNSW if
   the filter is too selective — the graph fragments and greedy
   traversal fails because the nodes that pass the filter aren't
   reachable through other passing nodes.
2. **Post-filter** (ANN top-K, then filter): you may lose all
   candidates if the filter is selective. Need to over-fetch wildly.
3. **In-graph filter** (traverse HNSW but only consider passing nodes
   during the walk): requires payload indexes and careful
   implementation. Qdrant does this well — their filterable HNSW
   dynamically widens the search when filter selectivity is high to
   maintain recall.

For finance retrieval — every query has temporal, source, and asset
filters — in-graph filtering matters more than raw ANN throughput.
**This is the underrated reason IMDR picks Qdrant** over alternatives
that bolt filtering on after the fact.

## Hybrid retrieval

Pure dense retrieval misses exact-term matches: tickers, currency
codes, MIFOR, OIS, ISO dates, CUSIPs. BM25 (sparse keyword retrieval,
scoring by term frequency × inverse document frequency with length
normalization) catches them. Production systems run both retrievers
in parallel and fuse:

* **Reciprocal Rank Fusion (RRF).** `score(d) = Σᵢ 1 / (k + rankᵢ(d))`
  across retrievers, k typically 60. No score normalization needed —
  robust and the default.
* **Learned weighted fusion.** If you have labeled (query, relevant
  doc) pairs, train weights. Better but needs data.

For our use cases — vendor emails matching prior templates, prediction-
market chunks tagged with macro themes, sell-side research notes —
hybrid is essentially mandatory. Pure dense will silently fail on
"USDKRW" queries because the embedding model treats it as a
low-information token.

## Reranking

ANN returns top-K candidates with bi-encoder scores (the embedding
similarity). For final ranking, run a cross-encoder over the top-K: a
single transformer that takes (query, doc) jointly and outputs a
relevance score. Models like `bge-reranker-v2-m3` (open) or Cohere
Rerank 3.5 / Amazon Rerank (managed).

Cross-encoders are 10–100× slower per pair but materially more
accurate — the model gets to attend across query and doc tokens
jointly, where bi-encoders compress each side independently into a
single vector before similarity is computed. You ANN to get top-100,
rerank to get top-10. The math is similar in spirit to going from a
dot-product approximation to the full inner product on the original
Hilbert space.

## The actual production query flow

```
1.  Query string  ─────────────────►  embedding (same model as corpus)
                                        │
2.                                      ▼
    Filter from metadata predicates (date, source, asset, theme)
                                        │
3.                                      ▼
    ANN search with in-graph filter ──► top-100 candidates
                                        │
4. (optional)                           ▼
    BM25 in parallel  ──► RRF fusion ─► top-100
                                        │
5.                                      ▼
    Cross-encoder rerank ─────────────► top-10
                                        │
6.                                      ▼
    Pass to LLM for generation  /  return as final result
```

The complexity sits in steps 2–4: getting filters fast and selective,
getting hybrid fusion right, and tuning HNSW parameters for your
recall/latency target. Step 5 is increasingly important — at production
quality bars, the gap between "ANN top-10" and "ANN top-100 → rerank
→ top-10" is often the difference between *this works* and *this
doesn't work*.

## The mental model worth keeping

**Retrieval is two-stage by necessity.** A fast, approximate,
embedding-space search to cut N down to K (where K is small, ~100),
then a slow, accurate, joint-attention scorer over those K.

* ANN is the cheap filter.
* The cross-encoder is the precise judge.

Same architectural pattern as IVF-PQ (coarse cluster filter, then PQ
distance), as candidate generation in recommender systems, as L1
cache vs main memory. It's the dominant idiom because the
hardware/cost asymmetry between fast-approximate and slow-precise is
enormous.

## Where IMDR sits today

| Stage | Status | Notes |
|---|---|---|
| 1. Query embedding | ✅ live | Provider-aware framing in `retrieve.py` (Voyage `input_type=query`, Gemini-001 `RETRIEVAL_QUERY`) |
| 2. Metadata filters | ✅ live | vendor / report_id / publish_date in `_build_filters()` |
| 3. ANN with in-graph filter | ✅ live | Qdrant HNSW (default M=16, ef_search=128) |
| 4. Hybrid (BM25 + RRF) | ⏭️ planned | Needed once tickers/CUSIPs/ISO codes start dominating queries |
| 5. Cross-encoder rerank | ⏭️ planned | Candidate: `bge-reranker-v2-m3` self-hosted, or Cohere Rerank 3.5 |
| Score floor | ✅ live | `--min-score` default 0.45 (empirically: ≥0.55 strong, 0.45–0.55 topical, <0.45 noise) |
| Per-report grouping | ✅ live | `--group-by-report` collapses multi-chunk hits |

Build order from here: stand up the MCP server on what we have (steps
1–3 + score floor are enough for a small corpus), then add hybrid
when ticker queries start failing, then rerank when precision becomes
the bottleneck.

---

# Tuning and testing

This section covers how to actually measure and improve retrieval
quality. The key idea: **you cannot tune what you do not measure**.
Every parameter below has the same workflow — define a held-out
evaluation set, fix one parameter, sweep it, plot the metric, pick
the knee.

## Build an evaluation set first

Before tuning anything, you need a held-out set of (query, relevant
chunk_ids) pairs. Without it, you are vibing.

**Minimum viable eval set**: 30–50 queries hand-labeled by you, each
with 1–5 known-relevant chunk_ids. Sources for queries:
* Real questions you've actually asked the corpus.
* Synthetic from titles — *"What does Goldman say about EM carry?"*
  with the EM Trader chunks marked relevant.
* Adversarial — a query whose answer is *not* in the corpus, with
  zero relevant chunks. Tests the score floor.

**Storage layout** (suggested):
```
playground/research/eval/
   queries.yml        # query string + list of relevant chunk_ids
   run_eval.py        # runs all queries, computes metrics
   reports/           # historical metric snapshots
```

A query entry looks like:
```yaml
- query: "USD swaption vol skew payer side"
  relevant: [chunk_id, ...]
  category: rates
  notes: "expects Goldman Rates Notes 2026-05-06"
```

**Hard rule**: never tune on the eval set. If you peek at it during
tuning, hold a second blind set out and report numbers on that.

## Metrics that matter

| Metric | What it measures | When to use |
|---|---|---|
| **recall@K** | Did the top-K contain at least one relevant chunk? | Primary metric for ANN tuning |
| **precision@K** | What fraction of top-K were relevant? | When K is small (10) and you care about clutter |
| **MRR** (mean reciprocal rank) | 1 / rank of the first relevant hit, averaged | When the user only reads the top hit |
| **nDCG@K** | Discounted gain — top hits weighted higher | When relevance is graded (1–3 scale, not binary) |
| **Latency p50 / p95 / p99** | Query time distribution | Production SLO; HNSW tuning trades recall for this |
| **Score distribution** | Histogram of top-1 scores across queries | Debugging — collapsed scores = embedding model regression |

For IMDR's current scale (~100 chunks → ~10K eventually), **recall@10
+ MRR** is enough. Add nDCG when you start grading relevance.

## Tuning the score floor (`--min-score`)

The single highest-leverage parameter for keeping the MCP server from
hallucinating citations.

**Method**:
1. Run the eval set; record top-1 score for each query.
2. Plot two histograms: scores when top-1 *is* relevant, scores when
   top-1 *is not* relevant.
3. Pick the threshold where the false-positive curve drops below ~5%.
   The two distributions usually overlap — there is no clean cut.
4. For adversarial (out-of-corpus) queries, top-1 should be *below*
   the threshold. If it isn't, the threshold is too low.

Current default `0.45` was set on a corpus of 81 chunks with
voyage-3-large; expect to re-tune at 1K+ chunks and per-model.
**Different embedding models have different score scales** —
gemini-embedding-2 typically scores higher than voyage-3-large for the
same query/doc pair. Keep one floor per `(model, dimensions)` pair.

## Tuning HNSW parameters

Qdrant exposes `hnsw_config` per collection. Defaults (M=16,
ef_construct=100, ef_search=128) are reasonable for <1M vectors.

**When to re-tune**:
* Corpus crosses 1M vectors → increase `M` to 32 if memory allows.
* p95 latency exceeds SLO → drop `ef_search`, accept ~1–2% recall loss.
* Recall@10 drops below target after a re-index → raise `ef_construct`.

**Sweep procedure**:
```
for ef_search in [32, 64, 128, 256, 512]:
    set ef_search; re-run eval; record (recall@10, p95_ms)
plot recall vs latency; pick the point on the Pareto frontier
```

`ef_search` is a **runtime** parameter — change without rebuilding the
index. `M` and `ef_construct` are **build-time** — change requires
re-indexing the whole collection (which IMDR can do from MSSQL via
`playground/research/reembed_report.py` over the affected report ids,
~minutes for current corpus).

**Reality check**: at current IMDR scale (~100 vectors per collection),
brute force is fine and HNSW parameters are noise. Tuning matters
once a collection crosses ~100K.

## Tuning chunk size and overlap

This is the parameter most people get wrong. It's set at *ingest*
time, not query time, so changes require re-chunking + re-embedding
the entire corpus.

Current settings (see [`chunk.py`](../../../playground/research/ingest/chunk.py)):
* **800 tokens / 100 overlap**, cl100k tokenizer, page-aware.

| Symptom | Likely cause | Fix |
|---|---|---|
| Snippets feel truncated mid-thought | Chunk too small | Raise to 1000–1200 |
| Embedding scores all clustered near 0.5 | Chunk too large (too many topics per chunk dilute the signal) | Drop to 500–600 |
| Concept spans page boundary, lost | Page-aware chunking severing context | Enable cross-page overlap, increase overlap to 150–200 |
| Tables come back as gibberish | Table flattening; not really a chunk-size issue | Detect tables in parse; use a separate chunker or skip |

**Validation**: before re-chunking the entire corpus, run on 5–10
representative reports, embed, and run the eval set. If recall@10
moves >5%, do the full re-index. If it moves <2%, don't bother.

## Embedding model A/B

IMDR keeps multiple models live in parallel collections (see
[qdrant.md](qdrant.md)) precisely so this comparison is cheap.

**Procedure**:
1. Same eval set, run against each `(model, dims)` collection.
2. Compute recall@10, MRR, p95 latency per model.
3. Pick winner per **query category** — rates queries may favor
   voyage-finance-2; cross-lingual EM queries may favor gemini-2.
4. If categories diverge, set up routing — but don't over-engineer
   until you have >20% category-level deltas.

Watch for: **score scale differences are NOT quality differences.**
voyage-3-large scoring 0.55 and gemini-2 scoring 0.75 on the same hit
does not mean gemini is "better." Compare ranks, not absolute scores.

## Testing methodology

### Regression suite

`run_eval.py` should:
1. Run all eval queries against the current Qdrant.
2. Compute recall@10, MRR, p95 latency.
3. Compare against a stored baseline (`reports/latest.json`).
4. **Fail loudly** if recall drops >2pp or p95 grows >50%.

Run before every:
* Embedding model change.
* Chunk parameter change.
* Qdrant version upgrade.
* Re-index from scratch.

### Adversarial / out-of-corpus tests

Include 5–10 queries whose answer is genuinely *not* in the corpus.
Examples for IMDR today: *"What's the price of Bitcoin?"*, *"Who is
the CEO of Tesla?"*. The system should return zero hits above
`min_score`. If it returns confident hits, the threshold is wrong or
the embedding is degenerate.

### Latency benchmarks

Don't average — measure p50/p95/p99. A retrieval system that's fast
on average but has a 2-second p99 will feel broken in Claude Desktop
because users hit the slow tail repeatedly.

Run with realistic concurrency: 10 parallel queries, 100 iterations,
record the distribution. Qdrant's `client.search` is not thread-safe
on the embedded backend — only meaningful on the remote backend.

### Watching production

Once the MCP is live, log every query with:
* Query text (or hash, if sensitive)
* Top-1 score
* Number of hits above threshold
* Latency

Two failure signals to alert on:
1. **Score collapse** — rolling top-1 score median drops by >0.1.
   Usually means the embedding service started returning wrong
   vectors, or a re-index corrupted a collection.
2. **Empty-result rate climbing** — fraction of queries with zero
   hits above threshold trending up. Either the corpus is going
   stale (no new ingest) or queries are drifting out of distribution.

## Common failure modes

| Symptom | Diagnosis | Fix |
|---|---|---|
| Top hits all from one report regardless of query | Over-ingestion of one document; or chunk count for that report >> rest | Group-by-report at retrieval; rebalance corpus |
| Tickers/CUSIPs return irrelevant results | Pure dense retrieval treating identifiers as low-info tokens | Add BM25 hybrid (step 4 in production flow) |
| Scores all 0.40–0.55, nothing above 0.6 | Likely a query-doc framing mismatch (ingest used `RETRIEVAL_DOCUMENT`, query forgot `RETRIEVAL_QUERY`) | Audit `_embed_query` framing per provider |
| Recall@10 great, user satisfaction terrible | Top-10 has the right doc but wrong rank | Add cross-encoder rerank (step 5) |
| Latency p99 >> p95 | Filter selectivity too high → HNSW falling back to scanning | Add payload index on the filter field; raise `ef_search` |

## TL;DR for IMDR right now

* **Build the eval set before doing anything else.** 30–50 queries,
  hand-labeled. This is the leverage point.
* `--min-score 0.45` is a guess; re-tune from a real eval set as soon
  as you have one.
* HNSW tuning is irrelevant at current scale (<10K vectors) — defaults
  are fine.
* Chunk size at 800/100 is reasonable; revisit only if eval shows a
  clear gap.
* Hybrid + rerank are the next architectural levers, not parameter tweaks.
