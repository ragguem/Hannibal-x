import httpx
import pytest

from hannibal_platform.context import request_id_var
from hannibal_platform.errors import DependencyUnavailable
from hannibal_platform.internal_client import InternalClient


def client_with(handler: httpx.MockTransport) -> InternalClient:
    return InternalClient("doctrine", "http://doctrine", token="tok", timeout_s=1, transport=handler)


async def test_sends_token_and_request_id() -> None:
    seen: dict[str, str] = {}

    def handle(request: httpx.Request) -> httpx.Response:
        seen.update(request.headers)
        return httpx.Response(200, json={"ok": True})

    token = request_id_var.set("req-abcdefgh")
    try:
        async with client_with(httpx.MockTransport(handle)) as client:
            response = await client.get("/health")
    finally:
        request_id_var.reset(token)
    assert response.status_code == 200
    assert seen["x-internal-token"] == "tok"
    assert seen["x-request-id"] == "req-abcdefgh"


async def test_server_error_becomes_dependency_unavailable() -> None:
    async with client_with(httpx.MockTransport(lambda _: httpx.Response(502))) as client:
        with pytest.raises(DependencyUnavailable) as caught:
            await client.get("/ask")
    assert caught.value.dependency == "doctrine"


async def test_transport_error_becomes_dependency_unavailable() -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    async with client_with(httpx.MockTransport(handle)) as client:
        with pytest.raises(DependencyUnavailable):
            await client.get("/ask")
        assert await client.is_healthy() is False


async def test_client_error_is_returned_to_caller() -> None:
    async with client_with(httpx.MockTransport(lambda _: httpx.Response(404))) as client:
        assert (await client.get("/missing")).status_code == 404
