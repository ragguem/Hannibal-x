"""Contrôle du jeton interne `X-Internal-Token` sur les services internes."""

import hmac
from collections.abc import Callable, Coroutine
from typing import Any

from fastapi import Request

from hannibal_platform.errors import Forbidden, Unauthenticated
from hannibal_platform.settings import BaseServiceSettings

HEADER = "X-Internal-Token"


def require_internal_token(settings: BaseServiceSettings) -> Callable[[Request], Coroutine[Any, Any, None]]:
    """Dépendance FastAPI. Sans jeton configuré, seuls les environnements locaux sont acceptés."""
    expected = settings.internal_token.get_secret_value() if settings.internal_token else None

    async def dependency(request: Request) -> None:
        if expected is None:
            if settings.is_local:
                return
            raise Forbidden("jeton interne non configuré hors environnement local")
        provided = request.headers.get(HEADER)
        if not provided:
            raise Unauthenticated("jeton interne absent")
        if not hmac.compare_digest(provided.encode(), expected.encode()):
            raise Forbidden("jeton interne invalide")

    return dependency
