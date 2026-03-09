"""Reusable HTTP client with retry, timeout, and structured logging."""

from __future__ import annotations

from typing import Any

import httpx
import structlog


class HTTPClient:
    """Thin wrapper around httpx.Client with retry and logging."""

    def __init__(
        self,
        base_url: str = "",
        timeout: int = 30,
        retries: int = 3,
        headers: dict[str, str] | None = None,
    ) -> None:
        self._log = structlog.get_logger("HTTPClient")
        transport = httpx.HTTPTransport(retries=retries)
        self._client = httpx.Client(
            base_url=base_url,
            timeout=timeout,
            transport=transport,
            headers=headers or {},
        )

    def get_json(self, path: str, params: dict[str, Any] | None = None) -> Any:
        """GET request, raise on HTTP errors, return parsed JSON."""
        self._log.info("http_get", path=path, params=params)
        resp = self._client.get(path, params=params)
        resp.raise_for_status()
        return resp.json()

    def get_text(self, path: str, params: dict[str, Any] | None = None) -> str:
        """GET request, return response text (e.g. CSV)."""
        self._log.info("http_get_text", path=path, params=params)
        resp = self._client.get(path, params=params)
        resp.raise_for_status()
        return resp.text

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> HTTPClient:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()
