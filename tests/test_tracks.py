from __future__ import annotations

import httpx


async def test_track_normalizes_nested_detail_and_netease_prefixed_id(app_factory) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/song/detail"
        assert request.url.params["ids"] == "123"
        return httpx.Response(
            200,
            json={
                "songs": [
                    {
                        "id": 123,
                        "name": "死ぬのがいいわ",
                        "ar": [{"name": "藤井風"}],
                        "al": {"name": "LOVE ALL SERVE ALL"},
                        "dt": 210_500,
                        "url": "https://cdn.example/123.mp3",
                    }
                ]
            },
        )

    _, api, upstream = app_factory(handler)
    try:
        response = await api.get("/tracks/netease:123")
    finally:
        await api.aclose()
        await upstream.client.aclose()

    assert response.status_code == 200
    assert response.json()["id"] == "123"
    assert response.json()["duration_seconds"] == 210
    assert response.json()["playable"] is True


async def test_missing_playback_url_is_explicitly_unplayable(app_factory) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/song/detail":
            return httpx.Response(
                200,
                json={
                    "songs": [
                        {"id": 9, "name": "何なんw", "ar": [{"name": "藤井風"}], "dt": 1000}
                    ]
                },
            )
        assert request.url.path == "/song/url/v1"
        assert request.url.params["level"] == "exhigh"
        return httpx.Response(200, json={"data": [{"id": 9, "url": None}]})

    _, api, upstream = app_factory(handler)
    try:
        response = await api.get("/tracks/9")
    finally:
        await api.aclose()
        await upstream.client.aclose()

    assert response.status_code == 200
    assert response.json()["playable"] is False
    assert response.json()["playback_url"] is None


async def test_malformed_track_and_unknown_id_do_not_leak_upstream_payload(app_factory) -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"songs": [{"name": "not enough metadata"}]})

    _, api, upstream = app_factory(handler)
    try:
        response = await api.get("/tracks/404")
    finally:
        await api.aclose()
        await upstream.client.aclose()

    assert response.status_code == 404
    assert response.json() == {"detail": "track not found"}
