"""Client HTTP vers un service interne : jeton, request_id, délai, erreur traduite."""

from types import TracebackType
from typing import Any, Self

import httpx

from hannibal_platform.context import current_request_id
from hannibal_platform.errors import DependencyUnavailable
from hannibal_platform.internal_auth import HEADER as TOKEN_HEADER
from hannibal_platform.logging import get_logger
from hannibal_platform.request_id import HEADER as REQUEST_ID_HEADER

log = get_logger(__name__)


class InternalClient:
    def __init__(
        self,
        dependency: str,
        base_url: str,
        *,
        token: str | None,
        timeout_s: float,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.dependency = dependency
        headers = {TOKEN_HEADER: token} if token else {}
        self._client = httpx.AsyncClient(
            base_url=base_url, headers=headers, timeout=timeout_s, transport=transport
        )

    async def request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        headers = dict(kwargs.pop("headers", None) or {})
        request_id = current_request_id()
        if request_id:
            headers[REQUEST_ID_HEADER] = request_id
        try:
            response = await self._client.request(method, path, headers=headers, **kwargs)
        except httpx.TimeoutException as exc:
            log.warning("dependency_timeout", dependency=self.dependency, path=path)
            raise DependencyUnavailable(self.dependency, "délai dépassé") from exc
        except httpx.TransportError as exc:
            log.warning("dependency_unreachable", dependency=self.dependency, path=path, error=str(exc))
            raise DependencyUnavailable(self.dependency, "injoignable") from exc
        if response.status_code >= 500:
            log.warning(
                "dependency_failed", dependency=self.dependency, path=path, status=response.status_code
            )
            raise DependencyUnavailable(self.dependency, f"réponse {response.status_code}")
        return response

    async def get(self, path: str, **kwargs: Any) -> httpx.Response:
        return await self.request("GET", path, **kwargs)

    async def post(self, path: str, **kwargs: Any) -> httpx.Response:
        return await self.request("POST", path, **kwargs)

    async def is_healthy(self) -> bool:
        try:
            response = await self.get("/health")
        except DependencyUnavailable:
            return False
        return response.status_code == 200

    async def aclose(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.aclose()
