from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

import httpx
import pytest

from netease_sidecar.app import create_app
from netease_sidecar.upstream import UpstreamClient

Handler = Callable[[httpx.Request], httpx.Response | Awaitable[httpx.Response]]


@pytest.fixture
def app_factory() -> Callable[[Handler], tuple[Any, httpx.AsyncClient, UpstreamClient]]:
    def factory(handler: Handler) -> tuple[Any, httpx.AsyncClient, UpstreamClient]:
        transport = httpx.MockTransport(handler)
        upstream_http = httpx.AsyncClient(transport=transport)
        upstream = UpstreamClient(
            "http://upstream.test",
            client=upstream_http,
        )
        app = create_app(upstream)
        api = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://sidecar.test")
        return app, api, upstream

    return factory

