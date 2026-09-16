from __future__ import annotations

import httpx
import pytest

from netease_sidecar.upstream import UpstreamTimeout


async def test_playback_returns_only_upstream_supplied_url(app_factory) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/song/url"
        assert request.url.params["id"] == "101"
        return httpx.Response(200, json={"data": [{"id": 101, "url": "https://cdn.example/101.mp3"}]})

    _, api, upstream = app_factory(handler)
    try:
        response = await api.get("/tracks/netease:101/playback")
    finally:
        await api.aclose()
        await upstream.client.aclose()

    assert response.status_code == 200
    assert response.json() == {
        "data": {"playback_url": "https://cdn.example/101.mp3"},
        "playable": True,
    }


async def test_playback_unavailable_is_not_manufactured(app_factory) -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": [{"id": 101, "url": None}]})

    _, api, upstream = app_factory(handler)
    try:
        response = await api.get("/tracks/101/playback")
    finally:
        await api.aclose()
        await upstream.client.aclose()

    assert response.status_code == 200
    assert response.json() == {"data": {"playback_url": None}, "playable": False}


async def test_non_2xx_is_sanitized_as_502(app_factory) -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(429, text="secret upstream body")

    _, api, upstream = app_factory(handler)
    try:
        response = await api.get("/tracks/101/playback")
    finally:
        await api.aclose()
        await upstream.client.aclose()

    assert response.status_code == 502
    assert response.json() == {"detail": "music upstream unavailable"}
    assert "secret" not in response.text


async def test_timeout_is_sanitized_as_504(app_factory) -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("provider secret")

    _, api, upstream = app_factory(handler)
    try:
        response = await api.get("/tracks/101/playback")
    finally:
        await api.aclose()
        await upstream.client.aclose()

    assert response.status_code == 504
    assert response.json() == {"detail": "music upstream timed out"}
    assert "provider secret" not in response.text


@pytest.mark.parametrize("payload", [{"data": []}, {"data": [{"id": 101, "url": ""}]}, {}])
async def test_empty_or_null_playback_payload_is_unplayable(app_factory, payload) -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    _, api, upstream = app_factory(handler)
    try:
        response = await api.get("/tracks/101/playback")
    finally:
        await api.aclose()
        await upstream.client.aclose()

    assert response.status_code == 200
    assert response.json()["playable"] is False


def test_timeout_error_remains_typed() -> None:
    assert issubclass(UpstreamTimeout, Exception)

