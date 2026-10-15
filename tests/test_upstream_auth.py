from __future__ import annotations

import httpx

from netease_sidecar.upstream import UpstreamClient, UpstreamError


async def test_optional_bearer_token_is_sent_only_to_upstream() -> None:
    seen: list[str | None] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.headers.get("Authorization"))
        return httpx.Response(200, json={"result": {"songs": []}})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    upstream = UpstreamClient(
        "https://music-upstream.example",
        bearer_token="test-secret",
        client=client,
    )
    try:
        await upstream.search("test", 1)
    finally:
        await client.aclose()

    assert seen == ["Bearer test-secret"]


async def test_bearer_token_is_optional() -> None:
    seen: list[str | None] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.headers.get("Authorization"))
        return httpx.Response(200, json={"result": {"songs": []}})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    upstream = UpstreamClient("http://127.0.0.1:3000", client=client)
    try:
        await upstream.search("test", 1)
    finally:
        await client.aclose()

    assert seen == [None]


async def test_upstream_error_does_not_include_bearer_token() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(401, text="Bearer test-secret")

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    upstream = UpstreamClient(
        "https://music-upstream.example",
        bearer_token="test-secret",
        client=client,
    )
    try:
        try:
            await upstream.search("test", 1)
        except UpstreamError as error:
            assert "test-secret" not in str(error)
        else:
            raise AssertionError("expected UpstreamError")
    finally:
        await client.aclose()


async def _seen_headers(upstream_kwargs: dict[str, str | None]) -> list[httpx.Headers]:
    seen: list[httpx.Headers] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.headers)
        return httpx.Response(200, json={"result": {"songs": []}})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    upstream = UpstreamClient("https://music-upstream.example", client=client, **upstream_kwargs)
    try:
        await upstream.search("test", 1)
        await upstream.playback("101")
    finally:
        await client.aclose()
    return seen


async def test_cookie_is_sent_as_header_never_in_url() -> None:
    seen = await _seen_headers({"cookie": "  MUSIC_U=fake-session; __csrf=fake-csrf \n"})

    assert [h.get("Cookie") for h in seen] == ["MUSIC_U=fake-session; __csrf=fake-csrf"] * 2


async def test_cookie_is_not_sent_when_unconfigured() -> None:
    for value in (None, "", "   "):
        seen = await _seen_headers({"cookie": value})
        assert [h.get("Cookie") for h in seen] == [None, None]


async def test_cookie_and_bearer_work_together() -> None:
    seen = await _seen_headers({"cookie": "MUSIC_U=fake", "bearer_token": "fake-bearer"})

    assert all(h["Authorization"] == "Bearer fake-bearer" for h in seen)
    assert all(h["Cookie"] == "MUSIC_U=fake" for h in seen)


async def test_cookie_is_not_in_url_or_error_or_repr() -> None:
    urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        urls.append(str(request.url))
        return httpx.Response(500, text="Cookie: MUSIC_U=fake-session")

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    upstream = UpstreamClient(
        "https://music-upstream.example", cookie="MUSIC_U=fake-session", client=client
    )
    try:
        try:
            await upstream.search("test", 1)
        except UpstreamError as error:
            assert "fake-session" not in str(error)
        else:
            raise AssertionError("expected UpstreamError")
    finally:
        await client.aclose()

    assert "fake-session" not in "".join(urls)
    assert "fake-session" not in repr(upstream)


def test_invalid_cookie_fails_without_echoing_value() -> None:
    for bad in ("MUSIC_U=a\r\nX-Evil: 1", "MUSIC_U=中文"):
        try:
            UpstreamClient("https://music-upstream.example", cookie=bad)
        except ValueError as error:
            assert "MUSIC_U" not in str(error).replace("NETEASE_UPSTREAM_COOKIE", "")
        else:
            raise AssertionError("expected ValueError")


async def test_app_reads_cookie_from_env_and_cookie_is_not_in_api_responses(monkeypatch) -> None:
    from netease_sidecar.app import create_app

    monkeypatch.setenv("NETEASE_UPSTREAM_COOKIE", "MUSIC_U=env-fake-session")
    app = create_app()
    seen: list[str | None] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.headers.get("Cookie"))
        return httpx.Response(200, json={"data": [{"id": 101, "url": "https://cdn.example/101.mp3"}]})

    app.state.upstream.client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    api = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://sidecar.test")
    try:
        response = await api.get(
            "/tracks/101/playback", headers={"Cookie": "MUSIC_U=caller-forged"}
        )
    finally:
        await api.aclose()
        await app.state.upstream.client.aclose()

    assert seen == ["MUSIC_U=env-fake-session"]
    assert "session" not in response.text and "forged" not in response.text


async def test_pasted_login_cookie_is_normalised_to_canonical_pairs() -> None:
    raw = (
        "MUSIC_R_T=fake-rt; Max-Age=2147483647; Expires=Tue, 14 Apr 2027 18:49:40 GMT; "
        "Path=/eapi/clientlog; HTTPOnly;MUSIC_U=fake-u==; Max-Age=15552000; Path=/; HTTPOnly;"
        "__csrf=fake-csrf; Max-Age=1296010; Path=/; Secure;NMTID=fake-nmtid; Path=/"
    )

    seen = await _seen_headers({"cookie": raw})

    assert [h.get("Cookie") for h in seen] == [
        "MUSIC_R_T=fake-rt; MUSIC_U=fake-u==; __csrf=fake-csrf; NMTID=fake-nmtid"
    ] * 2


def test_clean_cookie_without_pairs_fails_without_echoing_value() -> None:
    try:
        UpstreamClient("https://music-upstream.example", cookie="HTTPOnly; Secure; garbage")
    except ValueError as error:
        assert "garbage" not in str(error)
    else:
        raise AssertionError("expected ValueError")
