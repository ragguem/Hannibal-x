"""Métriques Prometheus : compteurs HTTP communs et route `/metrics` protégée par le jeton de collecte.

Pas d'identifiant de mission, d'utilisateur ou de commande en étiquette.
"""

import hmac
import time

from fastapi import APIRouter, Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, CollectorRegistry, Counter, Histogram, generate_latest
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from hannibal_platform.errors import Forbidden, Unauthenticated
from hannibal_platform.settings import BaseServiceSettings


class HttpMetrics:
    def __init__(self, registry: CollectorRegistry) -> None:
        self.requests = Counter(
            "http_requests_total", "Requêtes HTTP traitées", ["method", "route", "code"], registry=registry
        )
        self.duration = Histogram(
            "http_request_duration_seconds",
            "Durée des requêtes HTTP",
            ["method", "route"],
            registry=registry,
            buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30, 60, 120),
        )


def _route_template(scope: Scope) -> str:
    return str(getattr(scope.get("route"), "path", "unmatched"))


class MetricsMiddleware:
    def __init__(self, app: ASGIApp, metrics: HttpMetrics) -> None:
        self.app = app
        self.metrics = metrics

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["path"] == "/metrics":
            await self.app(scope, receive, send)
            return
        status = {"code": 500}
        started = time.perf_counter()

        async def capture(message: Message) -> None:
            if message["type"] == "http.response.start":
                status["code"] = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, capture)
        finally:
            route = _route_template(scope)
            method = scope["method"]
            self.metrics.requests.labels(method, route, str(status["code"])).inc()
            self.metrics.duration.labels(method, route).observe(time.perf_counter() - started)


def metrics_router(settings: BaseServiceSettings, registry: CollectorRegistry) -> APIRouter:
    router = APIRouter()
    expected = settings.metrics_token.get_secret_value() if settings.metrics_token else None

    @router.get("/metrics", include_in_schema=False)
    async def metrics(request: Request) -> Response:
        if expected is None:
            if not settings.is_local:
                raise Forbidden("jeton de collecte non configuré hors environnement local")
        else:
            auth = request.headers.get("Authorization", "")
            if not auth.startswith("Bearer "):
                raise Unauthenticated("jeton de collecte absent")
            if not hmac.compare_digest(auth.removeprefix("Bearer ").encode(), expected.encode()):
                raise Forbidden("jeton de collecte invalide")
        return Response(generate_latest(registry), media_type=CONTENT_TYPE_LATEST)

    return router
