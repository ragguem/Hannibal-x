"""Fabrique commune : journal, request_id, métriques, traducteur d'erreurs, santé."""

from typing import Any

from fastapi import FastAPI
from prometheus_client import CollectorRegistry

from hannibal_platform.errors import install_error_handlers
from hannibal_platform.health import health_router
from hannibal_platform.logging import configure_logging
from hannibal_platform.metrics import HttpMetrics, MetricsMiddleware, metrics_router
from hannibal_platform.request_id import RequestIdMiddleware
from hannibal_platform.settings import BaseServiceSettings


def create_service_app(
    settings: BaseServiceSettings,
    *,
    version: str,
    title: str,
    health_path: str = "/health",
    registry: CollectorRegistry | None = None,
    lifespan: Any = None,
    **fastapi_kwargs: Any,
) -> FastAPI:
    configure_logging(settings.service_name, settings.log_level, json=settings.log_json)
    registry = registry or CollectorRegistry()
    app = FastAPI(title=title, version=version, lifespan=lifespan, **fastapi_kwargs)
    app.state.settings = settings
    app.state.metrics_registry = registry
    install_error_handlers(app)
    app.add_middleware(MetricsMiddleware, metrics=HttpMetrics(registry))
    app.add_middleware(RequestIdMiddleware)
    app.include_router(health_router(settings.service_name, version, health_path))
    app.include_router(metrics_router(settings, registry))
    return app
