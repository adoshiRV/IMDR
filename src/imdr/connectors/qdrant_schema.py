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
      "chunk_id":      int,    # research.fact_chunk.id (= Qdrant point id)
      "report_id":     int,    # research.dim_report.id
      "vendor_code":   str,    # dbo.dim_vendor.code, INDEXED for filter
      "publish_date":  str,    # ISO yyyy-mm-dd, INDEXED for range filter
      "page_start":    int|None,
      "page_end":      int|None,
      "title":         str,
      "text_preview":  str,    # first ~240 chars of chunk_text
    }

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


def apply(client: QdrantClient | None = None, *, verbose: bool = True) -> list[str]:
    """Idempotently create every collection in :data:`SCHEMA`.

    Returns the list of collection names that were newly created.
    Existing collections are left alone; dim mismatch on an existing
    collection raises (caller must drop + recreate explicitly).
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
            if verbose:
                print(f"  ok   {spec.name}  (dim={spec.dimensions}, exists)")
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
