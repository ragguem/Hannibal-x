"""Lancement : `uvicorn --factory hannibal_api.socle.main:create_app`."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from hannibal_api import __version__
from hannibal_api.application.missions import MissionError
from hannibal_api.presentation.missions import missions_router, on_mission_error
from hannibal_api.presentation.system import system_router
from hannibal_api.socle.container import Container
from hannibal_api.socle.settings import ApiSettings
from hannibal_contracts import CONTRACTS_VERSION
from hannibal_platform.app import create_service_app


def create_app(settings: ApiSettings | None = None, container: Container | None = None) -> FastAPI:
    settings = settings or ApiSettings()
    container = container or Container(settings=settings)
    missions = container.missions()

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        await missions.shutdown()

    app = create_service_app(
        settings,
        version=__version__,
        title="Hannibal X API",
        health_path="/v1/health",
        lifespan=lifespan,
        docs_url="/v1/docs" if settings.is_local else None,
        openapi_url="/v1/openapi.json",
        redoc_url=None,
    )
    app.version = CONTRACTS_VERSION
    app.state.container = container
    app.include_router(
        system_router(container.check_readiness(), service=settings.service_name, version=__version__)
    )
    app.include_router(missions_router(missions, settings))
    app.add_exception_handler(MissionError, on_mission_error)
    return app
