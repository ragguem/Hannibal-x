from fastapi import APIRouter, Depends

from hannibal_contracts.rerank import RerankRequest, RerankResponse
from hannibal_platform.internal_auth import require_internal_token
from hannibal_platform.settings import BaseServiceSettings
from hannibal_rerank.application.rank import RankPassages


def ranking_router(rank: RankPassages, settings: BaseServiceSettings) -> APIRouter:
    router = APIRouter(dependencies=[Depends(require_internal_token(settings))])

    @router.post("/rerank", response_model=RerankResponse)
    async def rerank_passages(request: RerankRequest) -> RerankResponse:
        scores = await rank(request.queries, request.passages)
        return RerankResponse(scores=scores, model=rank.model_name)

    return router
