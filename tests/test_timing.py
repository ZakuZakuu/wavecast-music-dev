from __future__ import annotations

import httpx


async def test_timing_exposes_timestamps_without_lyric_text(app_factory) -> None:
    paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        paths.append(request.url.path)
        if request.url.path == "/song/detail":
            return httpx.Response(
                200,
                json={
                    "songs": [
                        {
                            "id": 123,
                            "name": "Timing Fixture",
                            "ar": [{"name": "Fixture Artist"}],
                            "dt": 60_000,
                        }
                    ]
                },
            )
        assert request.url.path == "/lyric"
        assert request.url.params["id"] == "123"
        return httpx.Response(
            200,
            json={
                "lrc": {
                    "lyric": (
                        "[00:05.00]first private lyric line\n"
                        "[00:12.50]second private lyric line\n"
                        "[00:30.00]third private lyric line"
                    )
                }
            },
        )

    _, api, upstream = app_factory(handler)
    try:
        response = await api.get("/tracks/netease:123/timing")
    finally:
        await api.aclose()
        await upstream.client.aclose()

    assert response.status_code == 200
    payload = response.json()
    assert payload["source_duration_seconds"] == 60
    assert payload["lyric_timestamps_available"] is True
    assert payload["lyric_lines"][0] == {"start_seconds": 5.0, "end_seconds": 12.0}
    assert payload["lyric_lines"][-1] == {"start_seconds": 30.0, "end_seconds": 37.0}
    assert payload["vocal_intervals"] == [
        {"start_seconds": 5.0, "end_seconds": 19.5},
        {"start_seconds": 30.0, "end_seconds": 37.0},
    ]
    assert "private lyric" not in response.text
    assert paths == ["/song/detail", "/lyric"]


async def test_timing_degrades_to_duration_when_lyrics_fail(app_factory) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/song/detail":
            return httpx.Response(
                200,
                json={
                    "songs": [
                        {
                            "id": 9,
                            "name": "No Lyrics",
                            "ar": [{"name": "Fixture Artist"}],
                            "dt": 184_000,
                        }
                    ]
                },
            )
        return httpx.Response(503, text="provider detail that must not leak")

    _, api, upstream = app_factory(handler)
    try:
        response = await api.get("/tracks/9/timing")
    finally:
        await api.aclose()
        await upstream.client.aclose()

    assert response.status_code == 200
    assert response.json() == {
        "source_duration_seconds": 184,
        "lyric_timestamps_available": False,
        "lyric_lines": [],
        "vocal_intervals": [],
    }
    assert "provider detail" not in response.text
