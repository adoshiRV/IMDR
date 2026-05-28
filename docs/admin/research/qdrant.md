# Qdrant — vector store for the research RAG corpus

Status: **live local server** — Qdrant 1.18.0 runs as a Windows
Service on `127.0.0.1:6333`, single-machine, no Docker. Service
install + lifecycle lives in [`docs/admin/qdrant/`](../qdrant/index.md).
Move to managed Qdrant Cloud only if/when the corpus or query traffic
outgrows a single box.

## Why Qdrant (the design call)

MSSQL `VARBINARY(MAX)` is fine for storing vectors but has no native
ANN — every cosine-similarity search is a full table scan + Python
brute-force loop. Latency math at our actual ingest rate:

| Corpus | Brute-force search latency |
|---|---|
| ~3K chunks (today) | < 100 ms |
| ~300K chunks (month 1) | ~1–2 s |
| ~1.8M chunks (month 6) | ~10 s — unusable |

Qdrant gives sub-100 ms search at any of those sizes via HNSW, plus
filter-on-payload (vendor / date / report) without us writing
SQL. Decision recorded 2026-05-08 (see chat history).

## Where it lives

### Server mode (the only mode in use)

Qdrant runs as a Windows Service on `127.0.0.1:6333`. Binary, web UI,
storage, snapshots, and logs all share one root at `C:\IMDR_LOCAL\qdrant\`.
Service install, lifecycle, config-source-of-truth, and backups live
in [`docs/admin/qdrant/`](../qdrant/index.md).

From the research side all you need is `IMDR_QDRANT_URL=http://127.0.0.1:6333`
in `.env` — `imdr.connectors.qdrant.get_qdrant_client()` and
`playground.research.ingest.qdrant_writer.QdrantWriter.from_env()`
both read it through pydantic-settings.

### Embedded fallback (legacy, decommissioned)

`QdrantWriter.from_env()` will fall back to an embedded file store at
`playground/research/qdrant_local/` if `local_path=` is passed
explicitly. The on-disk store was deleted on 2026-05-21 and the MCP
server no longer defaults to it — `mcp/research_server.py` raises a
clear error if neither `IMDR_QDRANT_URL` nor `IMDR_RESEARCH_QDRANT_PATH`
is set. The path remains in code as an opt-in for offline unit tests
only; live ingest and retrieval both target the server.

## Collection layout

One collection per `(model_name, dimensions)` tuple. Different
embedding models are **never** mixed in one collection — different
vector sizes and different similarity calibration. Naming convention:

```
research_<model_name_safe>_<dims>d
```

Active in the live server:

| Collection | Dims | Distance | Source model |
|---|---|---|---|
| `research_gemini_embedding_2_3072d` | 3072 | cosine | `gemini-embedding-2` |

To add a model, append a `CollectionSpec` to
[`qdrant_schema.SCHEMA`](../../../src/imdr/connectors/qdrant_schema.py)
and run `python -m imdr.connectors.qdrant_schema apply`.

## Point structure

| Field | Source | Notes |
|---|---|---|
| `point.id` | `research.fact_chunk.id` (BIGINT) | **The cross-system FK.** JOIN MSSQL on this to fetch chunk_text + report metadata. |
| `vector` | `Embedding.vector` (float32 LE bytes → list[float]) | Cosine similarity, unit-normalised by the embedding model |
| `payload.chunk_id` | mirror of point.id | redundancy for filter use |
| `payload.report_id` | `dim_report.id` | filter by report |
| `payload.vendor_code` | `dim_vendor.vendor_code` | filter by vendor |
| `payload.publish_date` | ISO `YYYY-MM-DD` | range filter |
| `payload.page_start`, `page_end` | from chunker | citation |
| `payload.title` | `dim_report.title` (truncated 200 chars) | citation |
| `payload.text_preview` | first 240 chars of chunk_text | quick inspection in dashboard / inspector |
| `payload.model_id` | `dim_embedding_model.id` | redundant w/ collection name; useful for cross-collection ops |

The ingest pipeline writes this in
[`pipeline.py`](../../../playground/research/ingest/pipeline.py)
after the MSSQL transaction commits — so `chunk_id` is always real.

## How to inspect

### Built-in inspector

```
python playground/research/inspect_qdrant.py
```

Lists every collection, vector counts + dims, and shows the most
recent N points with their payload. Optional flags:

```
python playground/research/inspect_qdrant.py --collection research_gemini_embedding_2_3072d
python playground/research/inspect_qdrant.py --sample 20
```

Example output:

```
qdrant: remote@http://127.0.0.1:6333

  collection: research_gemini_embedding_2_3072d
    vectors:    28  dims=3072  distance=Cosine
    most recent 5:
      chunk_id=2577   report_id=144  vendor=anz  date=2026-05-20  p.1-2
        title: NZD Update: What's happening in FX markets
        text:  for forecasts of NZD/USD across the upcoming...
```

### Retrieval CLI

```
python playground/research/retrieve.py "your question" --k 5 [--vendor X] [--report Y] [--since DATE]
```

Embeds query → Qdrant search (with filters) → JOIN MSSQL for full
chunk text + citations → prints ranked results. See
[`retrieve.py`](../../../playground/research/retrieve.py) and the
in-script docstring for full options.

### Web dashboard

```
http://localhost:6333/dashboard
```

GUI for browsing collections, running searches, viewing payloads. The
dashboard assets ship as a separate `dist-qdrant.zip` from the
qdrant-web-ui repo (the Windows qdrant binary doesn't bundle them);
the installer drops them at `C:\IMDR_LOCAL\qdrant\static\`, which the
service finds via NSSM `AppDirectory`.

### Direct file system

The directory tree under `C:\IMDR_LOCAL\qdrant\storage\` is Qdrant's
internal RocksDB-based store — opaque binaries. Don't edit by hand.
Inspecting via the Python client or dashboard is always the right path.

## Ingest behaviour (current state)

1. Pipeline phases unchanged through `db_write` (MSSQL).
2. After MSSQL commits, the pipeline gets `(report_id, was_inserted, chunk_id_by_index, model_id)` back from `write_report`.
3. If `was_inserted` and a `QdrantWriter` was passed in, the pipeline assembles `ChunkPoint`s using the returned chunk ids and upserts them into the per-model collection.
4. Idempotency is unchanged — content_hash check still gates everything; on dedup, Qdrant write is skipped (we already have the points keyed by the same chunk_ids).

Vectors are written **only to Qdrant**. The pipeline no longer
populates `research.fact_chunk_embedding.vector`; migration
[`055_drop_fact_chunk_embedding_vector.sql`](../../../migrations/055_drop_fact_chunk_embedding_vector.sql)
removes that column. Chunk text and metadata stay in
`research.fact_chunk`, which is enough to re-embed any report via
[`reembed_report.py`](../../../playground/research/reembed_report.py).

## Architecture diagram

```
                                 ┌─────────────────────────┐
                                 │    PDF on OneDrive       │
                                 │ (synced to SharePoint)   │
                                 └─────────────────────────┘
                                       ▲
                                       │ relative path stored as
                                       │ dim_report.pdf_path
                                       │
                ┌──────────────────────┴───────────────────────┐
                │                  MSSQL                       │
                │                                              │
                │  research.dim_report                         │
                │   └─ pdf_text NULL by default (saving)       │
                │                                              │
                │  research.fact_chunk                         │
                │   └─ chunk_text  ◄─── FK from Qdrant         │
                │      via JOIN ON c.id = qdrant.point.id      │
                │                                              │
                │  research.fact_chunk_embedding               │
                │   └─ vector column DROPPED in migration 055  │
                │      (chunk_id/model_id link rows remain     │
                │       as audit trail)                        │
                └──────────────────────┬───────────────────────┘
                                       │
                                       │ point.id == fact_chunk.id
                                       ▼
                                 ┌─────────────────────────┐
                                 │  Qdrant (local server)  │
                                 │  127.0.0.1:6333         │
                                 │                         │
                                 │  collection per model   │
                                 │   payload: report_id,   │
                                 │            vendor,      │
                                 │            publish_date,│
                                 │            page_*, ...  │
                                 └─────────────────────────┘
```

Read path (the retrieval CLI):

```
question
   │
   ▼
embed (same model used at ingest)
   │
   ▼
Qdrant search (with payload filters)
   │
   ▼ top-K chunk_ids
   │
   ▼
MSSQL JOIN: fetch chunk_text + report metadata
   │
   ▼
ranked, cited results
```
