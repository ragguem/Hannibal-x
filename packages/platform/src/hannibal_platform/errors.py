"""Exceptions typées et traducteur unique vers `{ code, message, request_id }`.

Un adaptateur attrape les erreurs de bibliothèque et lève une de ces exceptions.
Le message renvoyé est fixe pour un code ; le détail va dans le journal.
"""

from collections.abc import Mapping
from http import HTTPStatus
from typing import ClassVar

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from hannibal_platform.context import current_request_id
from hannibal_platform.logging import get_logger

log = get_logger(__name__)


class HannibalError(Exception):
    status: ClassVar[int] = HTTPStatus.INTERNAL_SERVER_ERROR
    code: ClassVar[str] = "internal"
    message: ClassVar[str] = "Erreur interne."

    def __init__(self, detail: str | None = None, **context: object) -> None:
        super().__init__(detail or self.message)
        self.detail = detail
        self.context = context

    def extra_body(self) -> Mapping[str, object]:
        return {}


class Unauthenticated(HannibalError):
    status = HTTPStatus.UNAUTHORIZED
    code = "unauthenticated"
    message = "Authentification requise."


class Forbidden(HannibalError):
    status = HTTPStatus.FORBIDDEN
    code = "forbidden"
    message = "Action non autorisée."


class NotFound(HannibalError):
    status = HTTPStatus.NOT_FOUND
    code = "not_found"
    message = "Ressource introuvable."


class Conflict(HannibalError):
    status = HTTPStatus.CONFLICT
    code = "conflict"
    message = "L'état de la ressource ne permet pas cette action."


class Throttled(HannibalError):
    status = HTTPStatus.TOO_MANY_REQUESTS
    code = "throttled"
    message = "Trop de demandes, réessayez plus tard."


class DependencyUnavailable(HannibalError):
    status = HTTPStatus.SERVICE_UNAVAILABLE
    code = "dependency_unavailable"
    message = "Un service nécessaire est indisponible."

    def __init__(self, dependency: str, detail: str | None = None) -> None:
        super().__init__(detail, dependency=dependency)
        self.dependency = dependency

    def extra_body(self) -> Mapping[str, object]:
        return {"dependency": self.dependency}


class DatabaseUnavailable(HannibalError):
    status = HTTPStatus.SERVICE_UNAVAILABLE
    code = "database_unavailable"
    message = "La base de données est indisponible."


def error_body(code: str, message: str, **extra: object) -> dict[str, object]:
    return {"code": code, "message": message, "request_id": current_request_id(), **extra}


async def _on_hannibal_error(_: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, HannibalError):
        raise exc
    log_method = log.error if exc.status >= HTTPStatus.INTERNAL_SERVER_ERROR else log.warning
    log_method("request_failed", code=exc.code, detail=exc.detail, **exc.context)
    return JSONResponse(error_body(exc.code, exc.message, **exc.extra_body()), status_code=exc.status)


async def _on_validation_error(_: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, RequestValidationError):
        raise exc
    log.warning("request_invalid", errors=exc.errors())
    return JSONResponse(
        error_body("invalid_request", "La requête est invalide."),
        status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
    )


async def _on_http_error(_: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, StarletteHTTPException):
        raise exc
    if exc.status_code == HTTPStatus.NOT_FOUND:
        body = error_body(NotFound.code, NotFound.message)
    elif exc.status_code == HTTPStatus.METHOD_NOT_ALLOWED:
        body = error_body("method_not_allowed", "Méthode non autorisée.")
    else:
        body = error_body("http_error", HTTPStatus(exc.status_code).phrase)
    return JSONResponse(body, status_code=exc.status_code, headers=exc.headers)


async def _on_unexpected(_: Request, exc: Exception) -> JSONResponse:
    log.exception("request_crashed", exc_type=type(exc).__name__)
    return JSONResponse(
        error_body("internal", "Erreur interne."), status_code=HTTPStatus.INTERNAL_SERVER_ERROR
    )


def install_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(HannibalError, _on_hannibal_error)
    app.add_exception_handler(RequestValidationError, _on_validation_error)
    app.add_exception_handler(StarletteHTTPException, _on_http_error)
    app.add_exception_handler(Exception, _on_unexpected)
