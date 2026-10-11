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


def test_chinese_title_comes_from_the_catalogs_translated_name() -> None:
    from netease_sidecar.normalize import normalize_track

    def item(**extra):
        return {"id": 1, "name": "あの夏へ", "artists": [{"name": "久石譲"}], "dt": 190000, **extra}

    assert normalize_track(item(tns=["回到那个夏天"])).title_zh == "回到那个夏天"
    # an alias that is only a short Chinese phrase is used when there is no translated name
    assert normalize_track(item(alia=["风之甬道"])).title_zh == "风之甬道"
    # an alias that describes the song is not a title
    assert normalize_track(item(alia=["动画电影《千与千寻》片尾曲"])).title_zh is None
    # an English translation is not a Chinese title; the next candidate is
    assert normalize_track(item(tns=["The Path of Wind", "风之甬道"])).title_zh == "风之甬道"
    assert normalize_track(item()).title_zh is None
    # a title that is already Chinese needs none
    chinese = {"id": 2, "name": "娜乌西卡安魂曲", "ar": [{"name": "久石譲"}], "dt": 1000}
    assert normalize_track({**chinese, "tns": ["别的"]}).title_zh is None
