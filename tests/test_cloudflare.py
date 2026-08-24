"""Tests for Cloudflare API client behavior."""

import asyncio

import pytest
from aiohttp import web

from autouam.core.cloudflare import REQUEST_TIMEOUT, CloudflareClient


def test_session_has_explicit_timeout():
    """Session must carry an explicit timeout, not aiohttp's 300s default."""
    client = CloudflareClient(api_token="tok", zone_id="zon")
    session = asyncio.run(client._get_session())
    try:
        assert session.timeout is not None
        assert session.timeout.total == 10
        assert session.timeout == REQUEST_TIMEOUT
    finally:
        asyncio.run(client.close())


@pytest.mark.asyncio
async def test_stalled_response_times_out_quickly(aiohttp_client_factory=None):
    """A stalled API response must abort near 10s, not hang for minutes."""

    async def slow_respond(request):
        await asyncio.sleep(60)

    app = web.Application()
    app.router.add_get("/client/v4/zones/zon", slow_respond)

    from aiohttp.test_utils import TestServer

    server = TestServer(app)
    await server.start_server()

    client = CloudflareClient(api_token="tok", zone_id="zon")
    client.base_url = str(server.make_url("/client/v4"))
    try:
        # The real timeout is 10s; cap the test at ~12s so CI fails loudly
        # if the client hangs instead of timing out.
        result = await asyncio.wait_for(_call_and_classify(client), timeout=12.0)
        assert result == "timeout", f"expected timeout near 10s, got: {result}"
    except asyncio.TimeoutError:
        pytest.fail("request was still pending after 12s - no client timeout")
    finally:
        await client.close()
        await server.close()


async def _call_and_classify(client: CloudflareClient) -> str:
    try:
        await client.get_zone_info()
        return "completed"
    except Exception as e:
        name = type(e).__name__
        return "timeout" if "Timeout" in name or "timeout" in str(e) else name
