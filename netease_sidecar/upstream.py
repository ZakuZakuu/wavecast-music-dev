"""Thin HTTP adapter for a separately running NetEase-compatible server.

Only this module knows the conventional NetEase-compatible paths.  Keeping the
paths and transport here makes replacing the local upstream cheap without
leaking its response format into the routes or WaveCast-facing models.
"""

from __future__ import annotations

from typing import Any

import httpx


class UpstreamError(Exception):
    """Safe, non-provider-specific upstream failure."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class UpstreamTimeout(UpstreamError):
    """The local upstream did not respond within the configured bound."""


class UpstreamClient:
    """HTTP client for the conventional local NetEase-compatible endpoints."""

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:3000",
        *,
        timeout_seconds: float = 10.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        # Local development should not route loopback requests through a user's
        # corporate/HTTP proxy (and keeps startup credential-free).
        self.client = client or httpx.AsyncClient(timeout=timeout_seconds, trust_env=False)
        self._owns_client = client is None

    async def search(self, query: str, limit: int) -> dict[str, Any]:
        return await self._get("/cloudsearch", params={"keywords": query, "limit": limit})

    async def readiness_probe(self) -> None:
        """Verify the upstream catalog route without requesting playback data."""
        await self._get(
            "/cloudsearch",
            params={"keywords": "__wavecast_readiness__", "limit": 1},
        )

    async def track(self, track_id: str) -> dict[str, Any]:
        return await self._get("/song/detail", params={"ids": track_id})

    async def playback(self, track_id: str) -> dict[str, Any]:
        return await self._get("/song/url", params={"id": track_id})

    async def aclose(self) -> None:
        if self._owns_client:
            await self.client.aclose()

    async def _get(self, path: str, *, params: dict[str, str | int]) -> dict[str, Any]:
        try:
            response = await self.client.get(
                f"{self.base_url}{path}",
                params=params,
                headers={"Accept": "application/json"},
                timeout=self.timeout_seconds,
            )
        except httpx.TimeoutException as error:
            raise UpstreamTimeout("upstream request timed out") from error
        except httpx.RequestError as error:
            raise UpstreamError("upstream request failed") from error

        if response.is_error:
            raise UpstreamError("upstream returned an error", status_code=response.status_code)
        try:
            payload = response.json()
        except ValueError as error:
            raise UpstreamError(
                "upstream returned malformed JSON", status_code=response.status_code
            ) from error
        if not isinstance(payload, dict):
            raise UpstreamError(
                "upstream returned an invalid payload", status_code=response.status_code
            )
        return payload
