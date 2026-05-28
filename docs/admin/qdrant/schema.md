# Qdrant — schema (collections, payload, sync)

## Collection naming

One collection per `(domain, embedding_model, dimensions)` tuple:

```
research_{slugified_model_name}_{dims}d
```

Active collection (the only one `apply` creates today):

| Collection | Model | Dims | MSSQL `dim_embedding_model.id` |
|---|---|---|---|
| `research_gemini_embedding_2_3072d` | `gemini-embedding-2` | 3072 | 3 |

Distance metric: **cosine**.

Two earlier collections (`research_voyage_3_large_1024d` and
`research_gemini_embedding_001_3072d`) existed in the schema until
2026-05-21 but were never populated by the live pipeline and were
dropped from the server when the schema was trimmed. The model rows
in `research.dim_embedding_model` (ids 1 and 2) remain as historical
lookups — adding a `CollectionSpec` back to the schema would revive
them.

Definitions are code-as-schema in
[`src/imdr/connectors/qdrant_schema.py`](../../../src/imdr/connectors/qdrant_schema.py).
Add a model by appending a `CollectionSpec`, then run:

```powershell
python -m imdr.connectors.qdrant_schema apply       # create new collection
python -m imdr.connectors.qdrant_schema status      # show drift
python -m imdr.connectors.qdrant_schema drop NAME   # destructive, no confirm
```

## Payload schema (research)

Every research point carries the same payload — kept small enough to
avoid bloating the per-vector overhead, but enough for filtered search
without round-tripping to MSSQL:

| Field | Type | Indexed? | Notes |
|---|---|---|---|
| `chunk_id` | int | (PK) | `research.fact_chunk.id`. Also the Qdrant point id. |
| `report_id` | int | yes | `research.dim_report.id`. Group-by report. |
| `vendor_code` | str | yes (keyword) | `dbo.dim_vendor.vendor_code` — e.g. `anz`, `goldman`. Vendor-scoped filters. |
| `publish_date` | str | yes (keyword) | ISO `yyyy-mm-dd`. Range filters work on keyword indexes in Qdrant. |
| `page_start` | int / null | — | First page of the chunk inside the source PDF. |
| `page_end` | int / null | — | Last page of the chunk. |
| `title` | str | — | Report title, truncated to 200 chars. Display only. |
| `text_preview` | str | — | First 240 chars of chunk text. Display only — do not search this. |
| `model_id` | int | — | `research.dim_embedding_model.id`. Audit / cross-collection ops. |

## Sync with MSSQL

**Vectors live only in Qdrant.** `research.fact_chunk_embedding` once
mirrored the vector bytes in `VARBINARY` for defence-in-depth, but the
ingest pipeline no longer writes to that table. ~187 legacy rows
remain from before the Qdrant-only switch (covering `report_id` 6–124
as of 2026-05-21); newer reports do not appear there. Migration
[`055_drop_fact_chunk_embedding_vector.sql`](../../../migrations/055_drop_fact_chunk_embedding_vector.sql)
drops the `vector` column; the (chunk_id, model_id) link rows survive
as a thin audit trail. The chunk text and metadata (chunk boundaries,
page spans, hash, token count) remain authoritative in
`research.fact_chunk` — re-embedding is always possible from there via
[`reembed_report.py`](../../../playground/research/reembed_report.py).

**Invariant.** Every Qdrant point id corresponds to exactly one
`research.fact_chunk.id`. The payload's `report_id` matches
`research.fact_chunk.report_id` and `vendor_code` matches
`dbo.dim_vendor.vendor_code` for that report.

**Direction of writes.**

- **Live ingest** (`playground/research/ingest/pipeline.py`): writes
  the MSSQL transaction first (`dim_report` + `fact_chunk`), commits,
  then upserts to Qdrant using the assigned `fact_chunk.id` values.
  If the Qdrant upsert fails the MSSQL rows still exist and the report
  will be flagged as "in MSSQL but unsearchable" until backfilled.
- **Backfill / repair** ([`playground/research/reembed_report.py`](../../../playground/research/reembed_report.py)):
  pulls chunks from MSSQL by `report_id`, re-embeds via the configured
  model, upserts into the per-model collection. Use after a Qdrant
  reset, after switching embedding models, or to fix any
  MSSQL-without-Qdrant rows.

**Repair.** If Qdrant disagrees with MSSQL for any reason
(crash mid-upsert, machine reset, schema change), the
right move is always: drop the affected Qdrant collection, recreate
via `qdrant_schema apply`, re-embed from MSSQL via `reembed_report.py`.
Don't try to reconcile by hand.

## Why no SQL-style migrations

Qdrant is schema-light: a collection is a `(dims, distance, payload
indexes, HNSW params)` tuple. Changing any of those usually means
recreating the collection. We treat the collection definitions as
declarative code (`qdrant_schema.py`), validate them with
`apply`/`status`, and re-sync from MSSQL on drop. No `001_…sql`-style
forward/backward migrations needed.
