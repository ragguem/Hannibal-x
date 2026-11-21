"""Lancement : `uvicorn --factory hannibal_api.socle.main:create_app`."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from hannibal_api import __version__
from hannibal_api.application.missions import MissionError
from hannibal_api.infrastructure.gpu_gate_metrics import expose_gpu_gate
from hannibal_api.presentation.audit import audit_router
from hannibal_api.presentation.doctrine import doctrine_router
from hannibal_api.presentation.missions import mission_runs_router, missions_router, on_mission_error
from hannibal_api.presentation.system import system_router
from hannibal_api.socle.container import Container
from hannibal_api.socle.settings import AdapterMode, ApiSettings
from hannibal_contracts import CONTRACTS_VERSION
from hannibal_platform.app import create_service_app
from hannibal_platform.errors import HannibalError
from hannibal_platform.logging import get_logger

log = get_logger(__name__)


def create_app(settings: ApiSettings | None = None, container: Container | None = None) -> FastAPI:
    settings = settings or ApiSettings()
    container = container or Container(settings=settings)
    missions = container.missions()
    dispatcher = container.dispatcher()

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        try:
            await missions.interrupt_unfinished()
            await dispatcher.reconcile()
        except HannibalError as error:
            log.warning("unfinished_work_not_checked", code=error.code, detail=error.detail)
        dispatcher.start()
        yield
        await dispatcher.stop()
        await missions.shutdown()
        if settings.adapters is AdapterMode.REAL:
            await container.sim_bridge().aclose()
            await container.asr_client().aclose()
            await container.doctrine_client().aclose()
        engine = container.database_engine()
        if engine is not None:
            await engine.dispose()

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
    expose_gpu_gate(app.state.metrics_registry, container.gpu_gate())
    app.include_router(
        system_router(container.check_readiness(), service=settings.service_name, version=__version__)
    )
    voice_orders = container.voice_orders()
    app.include_router(
        missions_router(
            missions,
            container.commands(),
            voice_orders,
            settings,
            stream_period_s=settings.mission_stream_period_s,
        )
    )
    app.include_router(mission_runs_router(missions, settings))
    app.include_router(audit_router(container.audit_trail(), voice_orders, settings))
    app.include_router(
        doctrine_router(
            container.query_doctrine(), container.search_glossary(), container.explain_command(), settings
        )
    )
    app.add_exception_handler(MissionError, on_mission_error)
    return app
