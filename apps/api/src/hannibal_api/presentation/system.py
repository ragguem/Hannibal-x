from http import HTTPStatus

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from hannibal_api.application.check_readiness import CheckReadiness
from hannibal_api.domain.readiness import OverallState
from hannibal_contracts.common import DependencyState, DependencyStatus, ErrorBody, Readiness


def system_router(check_readiness: CheckReadiness, *, service: str, version: str) -> APIRouter:
    router = APIRouter(prefix="/v1", tags=["santé"])

    @router.get(
        "/ready",
        response_model=Readiness,
        responses={
            HTTPStatus.SERVICE_UNAVAILABLE: {"model": Readiness},
            HTTPStatus.INTERNAL_SERVER_ERROR: {"model": ErrorBody},
        },
    )
    async def ready() -> JSONResponse:
        report = await check_readiness()
        body = Readiness(
            status=report.state.value,
            service=service,
            version=version,
            dependencies=[
                DependencyStatus(name=r.name, state=DependencyState(r.state.value), latency_ms=r.latency_ms)
                for r in report.dependencies
            ],
        )
        status = HTTPStatus.OK if report.state is OverallState.READY else HTTPStatus.SERVICE_UNAVAILABLE
        return JSONResponse(body.model_dump(mode="json"), status_code=status)

    return router
