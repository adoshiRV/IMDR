"""Declarative Qdrant collection schema for IMDR.

Qdrant has no SQL-migration story — collections are recreated/altered
in-place. We treat the set of collections as code: one
:class:`CollectionSpec` per (domain, embedding model, dims), applied
idempotently by :func:`apply`.

Collection naming
-----------------
``research_{slugified_model_name}_{dims}d``

Matches the convention used by the live ingest pipeline
(``playground/research/ingest/qdrant_writer.py``), so the collections
this module creates are the same ones the pipeline writes into.

Payload schema (research)
-------------------------
Every research point stores::

    {
      "chunk_id":         int,    # research.fact_chunk.id (= Qdrant point id)
      "report_id":        int,    # research.dim_report.id
      "vendor_code":      str,    # dbo.dim_vendor.code, INDEXED for filter
      "vendor_category":  str,    # sell_side|official_cb|official_ministry|... INDEXED
      "publish_date":     str,    # ISO yyyy-mm-dd, INDEXED for range filter
      "country_code":     str|None,  # ISO 2-char, INDEXED — set by filings ingest
      "doc_type":         str|None,  # release|minutes|report|outlook|speech|... INDEXED
      "stream":           str|None,  # vendor-specific stream id, INDEXED
      "page_start":       int|None,
      "page_end":         int|None,
      "title":            str,
      "text_preview":     str,    # first ~240 chars of chunk_text
    }

The 4 lower-case fields (vendor_category, country_code, doc_type, stream)
are populated by the govt-filings ingest path
(``src/imdr/research/filings.py``). For sell-side research points, only
the first three fields (vendor_code, publish_date, report_id) are
populated by the existing pipeline; the new indexes are still useful
because empty payload fields are filterable via Qdrant's IsNull.

Use
---
    python -m imdr.connectors.qdrant_schema apply       # create missing
    python -m imdr.connectors.qdrant_schema status      # show drift
    python -m imdr.connectors.qdrant_schema drop NAME   # destructive, confirm
"""
from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from typing import Final

from qdrant_client import QdrantClient
from qdrant_client.http import models as qm

from imdr.connectors.qdrant import build_qdrant_client


COLLECTION_PREFIX: Final[str] = "research_"


@dataclass(slots=True, frozen=True)
class CollectionSpec:
    """Declarative Qdrant collection definition.

    Fields map 1:1 onto :meth:`QdrantClient.create_collection` arguments.
    Add new payload indexes by appending to ``payload_indexes``.
    """
    model_name: str           # e.g. "gemini-embedding-2"
    dimensions: int           # vector size
    distance: qm.Distance = qm.Distance.COSINE
    payload_indexes: tuple[tuple[str, qm.PayloadSchemaType], ...] = (
        ("vendor_code", qm.PayloadSchemaType.KEYWORD),
        ("publish_date", qm.PayloadSchemaType.KEYWORD),
        ("report_id", qm.PayloadSchemaType.INTEGER),
        # Added 2026-06-10 for the govt-filings extension. Sell-side
        # points leave these payload fields unset; filings points set
        # all four. Mycroft/Lois filter on vendor_category to
        # include/exclude the official corpus.
        ("vendor_category", qm.PayloadSchemaType.KEYWORD),
        ("country_code", qm.PayloadSchemaType.KEYWORD),
        ("doc_type", qm.PayloadSchemaType.KEYWORD),
        ("stream", qm.PayloadSchemaType.KEYWORD),
    )

    @property
    def name(self) -> str:
        slug = re.sub(r"[^a-z0-9]+", "_", self.model_name.lower()).strip("_")
        return f"{COLLECTION_PREFIX}{slug}_{self.dimensions}d"


# Schema definition — only models currently in use. Other rows in
# research.dim_embedding_model are kept as historical lookups but their
# Qdrant collections aren't recreated here. To activate another model,
# append its CollectionSpec and run apply().
SCHEMA: Final[tuple[CollectionSpec, ...]] = (
    CollectionSpec("gemini-embedding-2", 3072),
)


def _existing(client: QdrantClient) -> dict[str, qm.CollectionInfo]:
    out: dict[str, qm.CollectionInfo] = {}
    for c in client.get_collections().collections:
        out[c.name] = client.get_collection(c.name)
    return out


def _create(client: QdrantClient, spec: CollectionSpec) -> None:
    client.create_collection(
        collection_name=spec.name,
        vectors_config=qm.VectorParams(size=spec.dimensions, distance=spec.distance),
    )
    for field, schema in spec.payload_indexes:
        client.create_payload_index(
            collection_name=spec.name,
            field_name=field,
            field_schema=schema,
        )


def _existing_payload_indexes(info: qm.CollectionInfo) -> set[str]:
    """Field names that already have payload indexes on a live collection."""
    schema = getattr(info, "payload_schema", None) or {}
    # Qdrant returns a dict[field_name, PayloadIndexInfo]; an indexed field has
    # ``data_type`` set. Field appearing as a key = already indexed.
    return {field for field in schema.keys()}


def apply(client: QdrantClient | None = None, *, verbose: bool = True) -> list[str]:
    """Idempotently create every collection in :data:`SCHEMA`.

    Returns the list of collection names that were newly created.
    Existing collections keep their data; any payload-index entries in
    the schema that are NOT yet present on the live collection are
    added in-place (Qdrant treats payload-index creation on existing
    collections as additive — points already in the collection get
    re-indexed lazily).

    Dim mismatch on an existing collection raises (caller must drop +
    recreate explicitly).
    """
    c = client or build_qdrant_client()
    existing = _existing(c)
    created: list[str] = []
    for spec in SCHEMA:
        if spec.name in existing:
            info = existing[spec.name]
            actual = _vector_size(info)
            if actual != spec.dimensions:
                raise RuntimeError(
                    f"collection {spec.name!r} exists with dim={actual}, "
                    f"schema declares dim={spec.dimensions}. "
                    f"Drop manually before re-applying."
                )
            # Add missing payload indexes in-place (additive, safe).
            already_indexed = _existing_payload_indexes(info)
            added_now: list[str] = []
            for field, schema_type in spec.payload_indexes:
                if field in already_indexed:
                    continue
                c.create_payload_index(
                    collection_name=spec.name,
                    field_name=field,
                    field_schema=schema_type,
                )
                added_now.append(field)
            if verbose:
                suffix = f", added indexes: {added_now}" if added_now else ""
                print(f"  ok   {spec.name}  (dim={spec.dimensions}, exists{suffix})")
            continue
        _create(c, spec)
        created.append(spec.name)
        if verbose:
            print(f"  new  {spec.name}  (dim={spec.dimensions})")
    return created


def _vector_size(info: qm.CollectionInfo) -> int:
    """Extract single-vector size from a CollectionInfo (no named vectors)."""
    params = info.config.params.vectors
    if hasattr(params, "size"):
        return int(params.size)
    raise RuntimeError("named-vector collections are not supported")


def status(client: QdrantClient | None = None) -> None:
    """Print schema vs. live collections for drift inspection."""
    c = client or build_qdrant_client()
    existing = _existing(c)
    declared = {s.name: s for s in SCHEMA}
    all_names = sorted(set(existing) | set(declared))
    for name in all_names:
        in_schema = name in declared
        in_live = name in existing
        if in_schema and in_live:
            spec = declared[name]
            actual = _vector_size(existing[name])
            mark = "ok" if actual == spec.dimensions else "DIM MISMATCH"
            print(f"  {mark:13} {name}  declared={spec.dimensions}d live={actual}d")
        elif in_schema:
            print(f"  {'missing':13} {name}  declared={declared[name].dimensions}d")
        else:
            actual = _vector_size(existing[name])
            print(f"  {'extra':13} {name}  live={actual}d  (not in schema)")


def drop(name: str, *, client: QdrantClient | None = None) -> None:
    """Delete a collection. No confirmation — caller must mean it."""
    c = client or build_qdrant_client()
    c.delete_collection(collection_name=name)
    print(f"  dropped {name}")


def _main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="python -m imdr.connectors.qdrant_schema")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("apply",  help="create missing collections idempotently")
    sub.add_parser("status", help="show declared vs. live collections")
    d = sub.add_parser("drop", help="delete a collection (destructive)")
    d.add_argument("name")
    args = p.parse_args(argv)

    if args.cmd == "apply":
        apply()
    elif args.cmd == "status":
        status()
    elif args.cmd == "drop":
        drop(args.name)
    return 0


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))
