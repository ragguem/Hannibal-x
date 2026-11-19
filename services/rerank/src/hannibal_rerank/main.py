"""Lancement : `uvicorn --factory hannibal_rerank.main:create_app`."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from hannibal_platform.app import create_service_app
from hannibal_rerank import __version__
from hannibal_rerank.application.ports import PairScorer
from hannibal_rerank.infrastructure.cross_encoder import CrossEncoderScorer
from hannibal_rerank.presentation.http import ranking_router
from hannibal_rerank.socle.composition import build_pair_scorer, build_rank_passages
from hannibal_rerank.socle.settings import RerankSettings


def create_app(settings: RerankSettings | None = None, scorer: PairScorer | None = None) -> FastAPI:
    settings = settings or RerankSettings()
    scorer = scorer or build_pair_scorer(settings)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        if isinstance(scorer, CrossEncoderScorer):
            await asyncio.to_thread(scorer.load)
        yield

    app = create_service_app(
        settings,
        version=__version__,
        title="Hannibal X rerank",
        lifespan=lifespan,
        docs_url="/docs" if settings.is_local else None,
        redoc_url=None,
    )
    app.include_router(ranking_router(build_rank_passages(settings, scorer), settings))
    return app
