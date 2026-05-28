# Qdrant — vector database for IMDR

Qdrant is the second persistent database in IMDR, alongside MSSQL.
MSSQL holds the report metadata and chunk text (`research.dim_report`,
`research.fact_chunk`, `research.dim_embedding_model`); Qdrant holds the
embedding vectors in a search-optimised HNSW index. **Every Qdrant
point.id must equal a `research.fact_chunk.id`** — chunks are the
system of record, Qdrant is the searchable index over them.

`research.fact_chunk_embedding` (legacy mirror of vector bytes) still
exists in the schema from migration 033 but is no longer populated by
the live pipeline. Migration `055_drop_fact_chunk_embedding_vector.sql`
drops the `vector` column; the (chunk_id, model_id) link rows remain
as a thin audit trail until a later migration retires the table.

## Files at a glance

| Where | What |
|---|---|
| `C:\IMDR_LOCAL\qdrant\qdrant.exe` | Binary (v1.18.0). Don't edit. |
| `C:\IMDR_LOCAL\qdrant\static\` | Web UI assets (dashboard at `/dashboard`). Loaded relative to the service's CWD. |
| `C:\IMDR_LOCAL\nssm\nssm.exe` | Service wrapper. Used to register/start/stop. |
| `C:\IMDR_LOCAL\qdrant\qdrant.log` | Service stdout (rotated at 10 MB). |
| `C:\IMDR_LOCAL\qdrant\qdrant.err.log` | Service stderr (rotated at 10 MB). |
| `C:\ProgramData\Qdrant\config.yaml` | Live config the service reads. Copied from repo by installer. |
| `C:\IMDR_LOCAL\qdrant\storage\` | Persistent vector data + HNSW index. Back this up. |
| `C:\IMDR_LOCAL\qdrant\snapshots\` | Output of explicit `client.create_snapshot()` calls. |
| `config/qdrant/production.yaml` (repo) | **Source of truth** for server config. Edit here. |
| `scripts/admin/install_qdrant.ps1` | Elevated installer / config-sync. Idempotent. |
| `src/imdr/connectors/qdrant.py` | `get_qdrant_client()` — only place that knows the URL/key. |
| `src/imdr/connectors/qdrant_schema.py` | Declarative collection definitions, `apply` / `status` / `drop` CLI. |
| `playground/research/reembed_report.py` | One-shot utility to re-embed MSSQL reports whose vectors got lost. |

## Sections

- **[setup.md](setup.md)** — Install from a clean machine (download, NSSM, service).
- **[operations.md](operations.md)** — Start/stop, health, logs, config refresh, backup.
- **[schema.md](schema.md)** — Collection naming, payload schema, indexes, sync with MSSQL.

## Rules

- **Loopback-only.** `service.host: 127.0.0.1` in the config. Never expose Qdrant on a routable interface from this machine.
- **MSSQL chunks are the truth.** Don't upsert a Qdrant point unless its `chunk_id` already exists in `research.fact_chunk`. The pipeline enforces this by committing the MSSQL transaction before calling `QdrantWriter.upsert_chunks`. If they disagree, drop the Qdrant collection and re-embed via `playground/research/reembed_report.py`.
- **Config edits go in the repo.** `config/qdrant/production.yaml` is tracked. After editing, re-run the installer (or copy by hand) to push to `C:\ProgramData\Qdrant\config.yaml`, then restart the service.
- **Don't run a second Qdrant process** with the same data dir. The store is single-writer and the file locks bite hard.
