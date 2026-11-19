from collections.abc import Sequence

from hannibal_contracts.rerank import RerankRequest, RerankResponse
from hannibal_platform.errors import DependencyUnavailable
from hannibal_platform.internal_client import InternalClient
from hannibal_platform.logging import get_logger

log = get_logger(__name__)


class RerankClient:
    """Service `rerank`. Absent ou lent : `None`, la question garde l'ordre des vecteurs (comme avant)."""

    def __init__(self, base_url: str, *, token: str | None, timeout_s: float) -> None:
        self._client = InternalClient("rerank", base_url, token=token, timeout_s=timeout_s)

    async def rerank(self, queries: Sequence[str], passages: Sequence[str]) -> list[float] | None:
        request = RerankRequest(queries=[q for q in queries if q][:3], passages=list(passages))
        try:
            response = await self._client.post("/rerank", json=request.model_dump(mode="json"))
        except DependencyUnavailable:
            return None
        if response.status_code != 200:
            log.warning("rerank_refused", status=response.status_code)
            return None
        return RerankResponse.model_validate_json(response.content).scores

    async def aclose(self) -> None:
        await self._client.aclose()


class NoReranker:
    async def rerank(self, queries: Sequence[str], passages: Sequence[str]) -> list[float] | None:
        return None
