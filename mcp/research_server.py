"""IMDR Research MCP Server — RAG retrieval over the research corpus.

Sibling to ``mcp/server.py`` (the read-only DB server). Exposes:

  - research_search:        semantic search over chunks → grouped citations
  - research_get_report:    full metadata + chunk listing for one report
  - research_list_vendors:  inventory of vendors with publication counts

The retrieval pipeline mirrors ``playground/research/retrieve.py``:

  1. Embed the query with the same model used at ingest time
     (Voyage or Gemini, switchable via IMDR_RESEARCH_EMBED_MODEL).
  2. ANN search Qdrant for the (model, dims) collection.
  3. Apply min_score floor and metadata filters.
  4. JOIN ``research.fact_chunk`` + ``research.dim_report`` + ``dbo.dim_vendor``
     for chunk_text + title + publish_date + vendor_code.
  5. Optionally group by report (default ON for MCP — Claude reads cleaner).

NOTE: This file is intentionally self-contained.  It does NOT import from
the imdr package (which pulls in pandas, structlog, etc.) so that startup
stays fast enough for Claude Desktop's ~5-second init timeout.
"""

from __future__ import annotations

import json
import os
import sys
import traceback
from datetime import date
from pathlib import Path

print("[imdr-research-mcp] server.py loading...", file=sys.stderr)

try:
    from mcp.server.fastmcp import FastMCP
    from sqlalchemy import bindparam, create_engine, text
    from sqlalchemy.engine import Engine
    print("[imdr-research-mcp] core imports OK", file=sys.stderr)
except Exception:
    traceback.print_exc(file=sys.stderr)
    sys.exit(1)


# ── Config (inline — avoids importing imdr.config.settings) ─────


def _load_env_file() -> None:
    """Best-effort load of relevant .env vars into os.environ."""
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if (
            key.startswith("IMDR_MSSQL_")
            or key.startswith("IMDR_RESEARCH_")
            or key.startswith("IMDR_QDRANT_")
            or key in ("IMDR_VOYAGE_KEY", "IMDR_GEMINI_KEY")
        ):
            os.environ.setdefault(key, value.strip())


try:
    _load_env_file()
    _DB_HOST = os.environ.get("IMDR_MSSQL_HOST", "localhost")
    _DB_PORT = os.environ.get("IMDR_MSSQL_PORT", "1433")
    _DB_NAME = os.environ.get("IMDR_MSSQL_DATABASE", "IMDR")
    # Research engine pinned to ODBC Driver 18 — same as ingest pipelines.
    _DB_DRIVER = os.environ.get(
        "IMDR_RESEARCH_MSSQL_DRIVER", "ODBC+Driver+18+for+SQL+Server"
    )
    _CONN_URL = (
        f"mssql+pyodbc://@{_DB_HOST}:{_DB_PORT}/{_DB_NAME}"
        f"?driver={_DB_DRIVER}&Trusted_Connection=yes"
        f"&Encrypt=yes&TrustServerCertificate=yes&LoginTimeout=60"
    )

    _QDRANT_URL = os.environ.get("IMDR_QDRANT_URL", "").strip()
    # Legacy embedded-mode fallback. The playground/research/qdrant_local/
    # tree was deleted on 2026-05-21; this path only resolves if someone
    # explicitly recreates it via IMDR_RESEARCH_QDRANT_PATH. Production
    # should always set IMDR_QDRANT_URL.
    _QDRANT_PATH = os.environ.get("IMDR_RESEARCH_QDRANT_PATH", "").strip()
    _DEFAULT_MODEL = os.environ.get(
        "IMDR_RESEARCH_EMBED_MODEL", "gemini-embedding-2"
    ).strip()
    _VOYAGE_KEY = os.environ.get("IMDR_VOYAGE_KEY", "").strip()
    _GEMINI_KEY = os.environ.get("IMDR_GEMINI_KEY", "").strip()

    print(
        f"[imdr-research-mcp] settings: host={_DB_HOST} "
        f"qdrant={_QDRANT_URL or _QDRANT_PATH} "
        f"default_model={_DEFAULT_MODEL}",
        file=sys.stderr,
    )
except Exception:
    print("[imdr-research-mcp] FATAL: settings load failed", file=sys.stderr)
    traceback.print_exc(file=sys.stderr)
    sys.exit(1)


# ── DB engine ──────────────────────────────────────────────────


try:
    _engine: Engine = create_engine(
        _CONN_URL,
        pool_size=2, max_overflow=4, pool_pre_ping=True, pool_timeout=30,
        echo=False,
    )
    print("[imdr-research-mcp] engine created", file=sys.stderr)
except Exception:
    print("[imdr-research-mcp] FATAL: engine creation failed", file=sys.stderr)
    traceback.print_exc(file=sys.stderr)
    sys.exit(1)


# ── Qdrant client ──────────────────────────────────────────────


_qdrant = None


def _get_qdrant():
    global _qdrant
    if _qdrant is not None:
        return _qdrant
    from qdrant_client import QdrantClient  # noqa: PLC0415

    if _QDRANT_URL:
        _qdrant = QdrantClient(url=_QDRANT_URL, prefer_grpc=False)
        print(f"[imdr-research-mcp] qdrant: remote {_QDRANT_URL}", file=sys.stderr)
    elif _QDRANT_PATH:
        _qdrant = QdrantClient(path=_QDRANT_PATH)
        print(f"[imdr-research-mcp] qdrant: embedded {_QDRANT_PATH}", file=sys.stderr)
    else:
        raise RuntimeError(
            "no Qdrant target configured — set IMDR_QDRANT_URL in .env "
            "(or IMDR_RESEARCH_QDRANT_PATH for the legacy embedded store)"
        )
    return _qdrant


# ── Embedding model registry (mirrors playground/research/ingest/embed.py) ─


_MODEL_SPEC: dict[str, dict] = {
    "voyage-3-large":         {"provider": "voyage", "dims": 1024},
    "voyage-finance-2":       {"provider": "voyage", "dims": 1024},
    "gemini-embedding-001":   {"provider": "google", "dims": 3072},
    "gemini-embedding-2":     {"provider": "google", "dims": 3072},
}


def _collection_name(model_name: str, dims: int) -> str:
    """Mirror QdrantWriter.from_env() naming: research_{model}_{dims}d.

    Underscores+lowercase, dots/dashes flattened.
    """
    safe = model_name.replace("-", "_").replace(".", "_").replace("/", "_").lower()
    return f"research_{safe}_{dims}d"


def _embed_query(text_value: str, model_name: str) -> list[float]:
    """Embed one query string with provider-aware framing.

    Voyage:        input_type='query'
    Gemini-001:    task_type='RETRIEVAL_QUERY'
    Gemini-2:      no task_type (model handles framing internally)
    """
    spec = _MODEL_SPEC.get(model_name)
    if not spec:
        raise ValueError(
            f"unknown embedding model: {model_name!r}. "
            f"known: {list(_MODEL_SPEC)}"
        )
    if spec["provider"] == "voyage":
        if not _VOYAGE_KEY:
            raise RuntimeError("IMDR_VOYAGE_KEY not set in .env / MCP env")
        import voyageai  # noqa: PLC0415
        client = voyageai.Client(api_key=_VOYAGE_KEY, max_retries=3)
        result = client.embed(
            texts=[text_value], model=model_name, input_type="query",
        )
        return list(result.embeddings[0])
    if spec["provider"] == "google":
        if not _GEMINI_KEY:
            raise RuntimeError("IMDR_GEMINI_KEY not set in .env / MCP env")
        from google import genai  # noqa: PLC0415
        from google.genai import types  # noqa: PLC0415
        client = genai.Client(api_key=_GEMINI_KEY)
        cfg_kwargs: dict = {"output_dimensionality": spec["dims"]}
        if model_name == "gemini-embedding-001":
            cfg_kwargs["task_type"] = "RETRIEVAL_QUERY"
        result = client.models.embed_content(
            model=model_name,
            contents=[types.Content(parts=[types.Part(text=text_value)])],
            config=types.EmbedContentConfig(**cfg_kwargs),
        )
        return list(result.embeddings[0].values)
    raise ValueError(f"unsupported provider {spec['provider']!r}")


# ── Filter builder (Qdrant payload → must conditions) ──────────


def _build_qdrant_filter(
    *,
    vendor: str | None,
    report_id: int | None,
    since: str | None,
    until: str | None,
):
    from qdrant_client.http.models import (  # noqa: PLC0415
        DatetimeRange, FieldCondition, Filter, MatchValue, Range,
    )
    must = []
    if vendor:
        must.append(FieldCondition(key="vendor_code", match=MatchValue(value=vendor)))
    if report_id is not None:
        must.append(FieldCondition(key="report_id", match=MatchValue(value=int(report_id))))
    if since or until:
        must.append(FieldCondition(
            key="publish_date",
            range=Range(gte=since, lte=until),
        ))
    return Filter(must=must) if must else None


# ── Tool implementations ──────────────────────────────────────


print("[imdr-research-mcp] startup complete", file=sys.stderr)
mcp = FastMCP("imdr-research")


@mcp.tool()
def research_search(
    query: str,
    k: int = 5,
    vendor: str | None = None,
    report_id: int | None = None,
    since: str | None = None,
    until: str | None = None,
    min_score: float = 0.45,
    model: str | None = None,
    group_by_report: bool = True,
) -> str:
    """Semantic search over the IMDR research RAG corpus.

    Embeds the query, ANN-searches Qdrant for the top-K most similar
    chunks, applies filters and a score floor, and returns citations
    grouped by report. Each citation includes vendor, publish_date,
    title, page range, similarity score, and a snippet.

    Args:
        query: natural-language question.
        k: top-K candidates to retrieve from Qdrant (post-filter cap).
        vendor: optional vendor_code filter (goldman / ms / nomura /
            anz / hsbc / barclays).
        report_id: optional dim_report.id filter (pin to one report).
        since: ISO date YYYY-MM-DD — earliest publish_date.
        until: ISO date YYYY-MM-DD — latest publish_date.
        min_score: drop hits below this cosine similarity (default 0.45).
            Empirically: >=0.55 strong, 0.45-0.55 topical, <0.45 noise.
        model: embedding model. Default uses IMDR_RESEARCH_EMBED_MODEL
            env or gemini-embedding-2. Known: gemini-embedding-2 (only
            model with a live Qdrant collection today), gemini-embedding-001,
            voyage-3-large, voyage-finance-2.
        group_by_report: if true (default), collapse multiple chunks
            from the same report into one entry showing all matched pages.

    Returns: JSON string with hit list, score, vendor, date, title,
        chunk_id, page range, snippet (~360 chars).
    """
    model_name = model or _DEFAULT_MODEL
    spec = _MODEL_SPEC.get(model_name)
    if not spec:
        return json.dumps({
            "error": f"unknown model {model_name!r}",
            "known_models": list(_MODEL_SPEC),
        })
    try:
        qvec = _embed_query(query, model_name)
    except Exception as exc:  # noqa: BLE001
        traceback.print_exc(file=sys.stderr)
        return json.dumps({"error": f"embed_query failed: {exc}"})

    qclient = _get_qdrant()
    coll = _collection_name(model_name, spec["dims"])
    flt = _build_qdrant_filter(
        vendor=vendor, report_id=report_id, since=since, until=until,
    )
    try:
        # Using query_points (newer API) with fallback to deprecated search.
        try:
            qresult = qclient.query_points(
                collection_name=coll, query=qvec, limit=k * 4, query_filter=flt,
                with_payload=True,
            )
            hits = qresult.points
        except Exception:
            hits = qclient.search(
                collection_name=coll, query_vector=qvec, limit=k * 4,
                query_filter=flt, with_payload=True,
            )
    except Exception as exc:  # noqa: BLE001
        traceback.print_exc(file=sys.stderr)
        return json.dumps({
            "error": f"qdrant search failed: {exc}",
            "collection": coll,
        })

    hits = [h for h in hits if (h.score or 0.0) >= min_score]
    if not hits:
        return json.dumps({
            "results": [], "n_hits": 0,
            "note": f"no hits >= min_score={min_score} in collection {coll}",
        })

    # Pull chunk_text + report metadata in one MSSQL call
    chunk_ids = [h.id for h in hits]
    sql = text("""
        SELECT c.id, c.chunk_text, c.page_start, c.page_end,
               r.id AS report_id, r.title, r.publish_date, v.vendor_code
        FROM research.fact_chunk c
        JOIN research.dim_report r ON r.id = c.report_id
        JOIN dbo.dim_vendor v ON v.id = r.vendor_id
        WHERE c.id IN :ids
    """).bindparams(bindparam("ids", expanding=True))
    try:
        with _engine.connect() as conn:
            rows = conn.execute(sql, {"ids": chunk_ids}).all()
    except Exception as exc:  # noqa: BLE001
        traceback.print_exc(file=sys.stderr)
        return json.dumps({"error": f"DB join failed: {exc}"})
    by_chunk = {row[0]: row for row in rows}

    def _row_dict(hit, row, *, snippet_chars=360):
        cid, ctext, pstart, pend, rid, title, pdate, vcode = row
        snip = (ctext or "").strip().replace("\n", " ")
        if len(snip) > snippet_chars:
            snip = snip[:snippet_chars].rstrip() + "..."
        return {
            "score": round(hit.score or 0.0, 4),
            "vendor": vcode, "publish_date": str(pdate),
            "title": title, "report_id": rid, "chunk_id": cid,
            "page_start": pstart, "page_end": pend,
            "snippet": snip,
        }

    if group_by_report:
        groups: dict = {}
        for h in hits:
            row = by_chunk.get(h.id)
            if not row:
                continue
            rid = row[4]
            g = groups.setdefault(rid, {
                "report_id": rid,
                "vendor": row[7], "publish_date": str(row[6]), "title": row[5],
                "best_score": h.score or 0.0,
                "matched_pages": set(),
                "chunks": [],
            })
            g["best_score"] = max(g["best_score"], h.score or 0.0)
            if row[2] is not None:
                g["matched_pages"].add(f"{row[2]}-{row[3]}")
            g["chunks"].append(_row_dict(h, row))
        # Order groups by best score desc, take top K
        ordered = sorted(
            groups.values(), key=lambda g: -g["best_score"]
        )[:k]
        for g in ordered:
            g["matched_pages"] = sorted(g["matched_pages"])
            g["best_score"] = round(g["best_score"], 4)
            g["n_chunks_matched"] = len(g["chunks"])
            # Keep only the top-1 snippet per group to keep response compact;
            # caller can use research_get_report for full text.
            g["chunks"] = sorted(
                g["chunks"], key=lambda c: -c["score"]
            )[:1]
        return json.dumps({
            "model": model_name, "collection": coll,
            "n_hits": len(ordered),
            "results": ordered,
        }, default=str)

    # Ungrouped — top-K by raw score
    out = []
    for h in hits[:k]:
        row = by_chunk.get(h.id)
        if row is None:
            continue
        out.append(_row_dict(h, row))
    return json.dumps({
        "model": model_name, "collection": coll,
        "n_hits": len(out), "results": out,
    }, default=str)


@mcp.tool()
def research_get_report(report_id: int) -> str:
    """Full metadata + chunk inventory for one research report.

    Use this after research_search to pull the complete chunk list
    (and full text) for a report whose top-1 snippet looked promising.

    Args:
        report_id: research.dim_report.id (also returned by research_search).

    Returns: JSON with title, vendor, publish_date, asset_class,
        pdf_path, page_count, plus the full chunk list with
        chunk_id, page_start/end, and chunk_text.
    """
    sql_meta = text("""
        SELECT r.id, r.title, r.publish_date, r.asset_class, r.region,
               r.pdf_path, r.page_count, v.vendor_code
        FROM research.dim_report r
        JOIN dbo.dim_vendor v ON v.id = r.vendor_id
        WHERE r.id = :id
    """)
    sql_chunks = text("""
        SELECT id, chunk_index, page_start, page_end, chunk_text
        FROM research.fact_chunk
        WHERE report_id = :id
        ORDER BY chunk_index
    """)
    try:
        with _engine.connect() as conn:
            meta_row = conn.execute(sql_meta, {"id": report_id}).first()
            if meta_row is None:
                return json.dumps({"error": f"report_id {report_id} not found"})
            chunk_rows = conn.execute(sql_chunks, {"id": report_id}).all()
    except Exception as exc:  # noqa: BLE001
        traceback.print_exc(file=sys.stderr)
        return json.dumps({"error": f"DB read failed: {exc}"})

    return json.dumps({
        "report_id": meta_row[0],
        "title": meta_row[1],
        "publish_date": str(meta_row[2]),
        "asset_class": meta_row[3],
        "region": meta_row[4],
        "pdf_path": meta_row[5],
        "page_count": meta_row[6],
        "vendor": meta_row[7],
        "n_chunks": len(chunk_rows),
        "chunks": [
            {
                "chunk_id": r[0],
                "chunk_index": r[1],
                "page_start": r[2],
                "page_end": r[3],
                "text": r[4],
            }
            for r in chunk_rows
        ],
    }, default=str)


@mcp.tool()
def research_list_vendors() -> str:
    """List vendors that have research reports ingested + counts.

    Useful for discovering valid ``vendor`` filter values for
    research_search.
    """
    sql = text("""
        SELECT v.vendor_code, v.display_name, COUNT(r.id) AS n_reports,
               MIN(r.publish_date) AS earliest, MAX(r.publish_date) AS latest
        FROM dbo.dim_vendor v
        LEFT JOIN research.dim_report r ON r.vendor_id = v.id
        WHERE v.is_active = 1
        GROUP BY v.vendor_code, v.display_name
        HAVING COUNT(r.id) > 0
        ORDER BY n_reports DESC
    """)
    try:
        with _engine.connect() as conn:
            rows = conn.execute(sql).all()
    except Exception as exc:  # noqa: BLE001
        traceback.print_exc(file=sys.stderr)
        return json.dumps({"error": f"DB read failed: {exc}"})

    return json.dumps({
        "vendors": [
            {
                "vendor_code": r[0],
                "display_name": r[1],
                "n_reports": r[2],
                "earliest": str(r[3]) if r[3] else None,
                "latest": str(r[4]) if r[4] else None,
            }
            for r in rows
        ],
    }, default=str)


if __name__ == "__main__":
    mcp.run()
