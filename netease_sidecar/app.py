"""FastAPI application exposing a stable WaveCast-facing music contract."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Query

from .models import NormalizedTrack
from .normalize import normalize_search, normalize_track_payload, playback_url
from .upstream import UpstreamClient, UpstreamError, UpstreamTimeout


def create_app(upstream: UpstreamClient | None = None) -> FastAPI:
    configured_upstream = upstream or UpstreamClient(
        base_url=os.getenv("NETEASE_UPSTREAM_BASE_URL", "http://127.0.0.1:3000"),
        timeout_seconds=_timeout_from_env(),
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        try:
            yield
        finally:
            await configured_upstream.aclose()

    app = FastAPI(title="WaveCast NetEase music-dev sidecar", lifespan=lifespan)
    app.state.upstream = configured_upstream

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/search")
    async def search(
        query: str = Query(min_length=1),
        limit: int = Query(default=5, ge=1, le=50),
    ) -> dict[str, list[NormalizedTrack]]:
        payload = await _call(lambda: configured_upstream.search(query, limit))
        return {"tracks": normalize_search(payload)[:limit]}

    @app.get("/tracks/{track_id}")
    async def track(track_id: str) -> NormalizedTrack:
        normalized_id = _normalize_id(track_id)
        if not normalized_id:
            raise HTTPException(status_code=404, detail="track not found")
        payload = await _call(lambda: configured_upstream.track(normalized_id))
        normalized = normalize_track_payload(payload)
        if normalized is None:
            raise HTTPException(status_code=404, detail="track not found")
        if normalized.playback_url is None:
            track_id_for_playback = normalized.id
            playback_payload = await _call(
                lambda: configured_upstream.playback(track_id_for_playback)
            )
            url = playback_url(playback_payload)
            if url:
                normalized = normalized.model_copy(
                    update={"playback_url": url, "playable": True}
                )
        return normalized

    @app.get("/tracks/{track_id}/playback")
    async def track_playback(track_id: str) -> dict[str, object]:
        normalized_id = _normalize_id(track_id)
        if not normalized_id:
            raise HTTPException(status_code=404, detail="track not found")
        payload = await _call(lambda: configured_upstream.playback(normalized_id))
        url = playback_url(payload)
        return {"data": {"playback_url": url}, "playable": bool(url)}

    return app


async def _call(operation: Callable[[], Awaitable[dict[str, Any]]]) -> dict[str, Any]:
    # Kept as a small route boundary so provider failures never leak upstream bodies.
    try:
        result = await operation()
    except UpstreamTimeout as error:
        raise HTTPException(status_code=504, detail="music upstream timed out") from error
    except UpstreamError as error:
        raise HTTPException(status_code=502, detail="music upstream unavailable") from error
    return result


def _normalize_id(track_id: str) -> str:
    value = track_id.strip()
    return value.removeprefix("netease:")


def _timeout_from_env() -> float:
    raw = os.getenv("NETEASE_UPSTREAM_TIMEOUT_SECONDS", "10")
    try:
        value = float(raw)
    except ValueError:
        return 10.0
    return value if value > 0 else 10.0


app = create_app()
