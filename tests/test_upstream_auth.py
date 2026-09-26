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
