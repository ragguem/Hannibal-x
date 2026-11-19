"""Lancement : `uvicorn --factory hannibal_doctrine.main:create_app`."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from hannibal_doctrine import __version__
from hannibal_doctrine.presentation.http import doctrine_router
from hannibal_doctrine.socle.composition import DoctrineAdaptersSet, build_adapters, build_use_cases
from hannibal_doctrine.socle.settings import DoctrineSettings
from hannibal_platform.app import create_service_app


def create_app(
    settings: DoctrineSettings | None = None, adapters: DoctrineAdaptersSet | None = None
) -> FastAPI:
    settings = settings or DoctrineSettings()
    adapters = adapters or build_adapters(settings)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        for adapter in adapters.closables:
            await adapter.aclose()

    app = create_service_app(
        settings,
        version=__version__,
        title="Hannibal X doctrine",
        lifespan=lifespan,
        docs_url="/docs" if settings.is_local else None,
        redoc_url=None,
    )
    app.include_router(doctrine_router(build_use_cases(settings, adapters), settings))
    return app
