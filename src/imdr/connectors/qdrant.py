"""Qdrant vector-DB client factory.

Mirrors the role of :mod:`imdr.connectors.mssql` for the vector store:
a single helper that reads settings, builds a client, and is the only
place that knows how to authenticate against Qdrant.

Server lifecycle is managed outside Python — Qdrant runs as a Windows
Service (NSSM) bound to 127.0.0.1:6333. See ``docs/admin/qdrant/setup.md``.
"""
from __future__ import annotations

from functools import lru_cache

from qdrant_client import QdrantClient

from imdr.config.settings import Settings, get_settings


def build_qdrant_client(settings: Settings | None = None) -> QdrantClient:
    """Construct a :class:`QdrantClient` from project settings.

    Returns a fresh client each call (callers manage lifecycle). For a
    cached singleton, use :func:`get_qdrant_client`.
    """
    s = settings or get_settings()
    kwargs: dict = {"url": s.qdrant_url, "timeout": s.qdrant_timeout}
    if s.qdrant_api_key:
        kwargs["api_key"] = s.qdrant_api_key
    return QdrantClient(**kwargs)


@lru_cache(maxsize=1)
def get_qdrant_client() -> QdrantClient:
    """Cached :class:`QdrantClient` for scripts and CLI entry points."""
    return build_qdrant_client()


def ping(client: QdrantClient | None = None) -> bool:
    """Cheap liveness check — returns True iff Qdrant responds.

    Raises the underlying transport error on failure so callers can log
    a useful message; use :func:`is_alive` for a swallowed-error variant.
    """
    c = client or get_qdrant_client()
    c.get_collections()
    return True


def is_alive(client: QdrantClient | None = None) -> bool:
    """Swallowed-error variant of :func:`ping` — never raises."""
    try:
        return ping(client)
    except Exception:  # noqa: BLE001
        return False
