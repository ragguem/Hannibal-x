from fastapi import APIRouter
from pydantic import BaseModel


class Health(BaseModel):
    status: str
    service: str
    version: str


def health_router(service: str, version: str, path: str = "/health") -> APIRouter:
    """Vivacité : le processus répond. La disponibilité des dépendances est l'affaire de `/ready`."""
    router = APIRouter()

    @router.get(path, response_model=Health, tags=["santé"])
    async def health() -> Health:
        return Health(status="ok", service=service, version=version)

    return router
