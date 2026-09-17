from __future__ import annotations

import httpx


async def test_health_is_liveness_only(app_factory) -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        raise AssertionError("health must not call the upstream")

    _, api, upstream = app_factory(handler)
    try:
        response = await api.get("/health")
    finally:
        await api.aclose()
        await upstream.client.aclose()

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_ready_checks_upstream_catalog_metadata(app_factory) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/cloudsearch"
        assert request.url.params["keywords"] == "__wavecast_readiness__"
        assert request.url.params["limit"] == "1"
        return httpx.Response(200, json={"result": {"songs": []}})

    _, api, upstream = app_factory(handler)
    try:
        response = await api.get("/ready")
    finally:
        await api.aclose()
        await upstream.client.aclose()

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


async def test_ready_hides_upstream_connection_failure(app_factory) -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("secret upstream URL and token", request=httpx.Request("GET", "http://upstream.test"))

    _, api, upstream = app_factory(handler)
    try:
        response = await api.get("/ready")
    finally:
        await api.aclose()
        await upstream.client.aclose()

    assert response.status_code == 502
    assert response.json() == {"detail": "music upstream unavailable"}
    assert "secret" not in response.text


async def test_ready_hides_upstream_timeout(app_factory) -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("secret upstream URL and token", request=httpx.Request("GET", "http://upstream.test"))

    _, api, upstream = app_factory(handler)
    try:
        response = await api.get("/ready")
    finally:
        await api.aclose()
        await upstream.client.aclose()

    assert response.status_code == 504
    assert response.json() == {"detail": "music upstream timed out"}
    assert "secret" not in response.text


async def test_search_normalizes_chinese_metadata_and_ms_duration(app_factory) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/cloudsearch"
        assert request.url.params["keywords"] == "藤井風"
        assert request.url.params["limit"] == "3"
        return httpx.Response(
            200,
            json={
                "result": {
                    "songs": [
                        {
                            "id": 101,
                            "name": "何なんw",
                            "ar": [{"name": "藤井風"}, {"name": "ゲスト"}],
                            "al": {"name": "HELP EVER HURT NEVER"},
                            "dt": 185_000,
                            "url": "https://cdn.example/101.mp3",
                        },
                        {
                            "id": "102",
                            "name": "死ぬのがいいわ",
                            "artists": [{"name": "Fujii Kaze"}],
                            "duration_ms": "240000",
                        },
                    ]
                }
            },
        )

    _, api, upstream = app_factory(handler)
    try:
        response = await api.get("/search", params={"query": "藤井風", "limit": 3})
    finally:
        await api.aclose()
        await upstream.client.aclose()

    assert response.status_code == 200
    assert response.json() == {
        "tracks": [
            {
                "id": "101",
                "title": "何なんw",
                "artist": "藤井風, ゲスト",
                "duration_seconds": 185,
                "playable": True,
                "album": "HELP EVER HURT NEVER",
                "playback_url": "https://cdn.example/101.mp3",
            },
            {
                "id": "102",
                "title": "死ぬのがいいわ",
                "artist": "Fujii Kaze",
                "duration_seconds": 240,
                "playable": False,
                "album": None,
                "playback_url": None,
            },
        ]
    }


async def test_empty_search_is_a_stable_empty_list(app_factory) -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"result": {"songs": []}})

    _, api, upstream = app_factory(handler)
    try:
        response = await api.get("/search", params={"query": "不存在", "limit": 5})
    finally:
        await api.aclose()
        await upstream.client.aclose()

    assert response.status_code == 200
    assert response.json() == {"tracks": []}
