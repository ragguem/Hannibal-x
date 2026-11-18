"""Lancement : `uvicorn --factory hannibal_api.socle.main:create_app`."""

from fastapi import FastAPI

from hannibal_api import __version__
from hannibal_api.presentation.system import system_router
from hannibal_api.socle.container import Container
from hannibal_api.socle.settings import ApiSettings
from hannibal_platform.app import create_service_app


def create_app(settings: ApiSettings | None = None) -> FastAPI:
    settings = settings or ApiSettings()
    container = Container(settings=settings)
    app = create_service_app(
        settings,
        version=__version__,
        title="Hannibal X API",
        health_path="/v1/health",
        docs_url="/v1/docs" if settings.is_local else None,
        openapi_url="/v1/openapi.json",
        redoc_url=None,
    )
    app.state.container = container
    app.include_router(
        system_router(container.check_readiness(), service=settings.service_name, version=__version__)
    )
    return app
