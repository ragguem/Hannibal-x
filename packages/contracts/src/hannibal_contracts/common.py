from enum import StrEnum

from pydantic import Field

from hannibal_contracts.base import ContractModel


class ErrorBody(ContractModel):
    code: str = Field(description="Code stable, en snake_case, documenté par route")
    message: str = Field(description="Message lisible, fixe pour un code")
    request_id: str | None = Field(description="Identifiant de la requête, à citer au support")
    dependency: str | None = Field(default=None, description="Service en cause pour `dependency_unavailable`")


class Health(ContractModel):
    status: str
    service: str
    version: str


class DependencyState(StrEnum):
    UP = "up"
    DOWN = "down"
    DISABLED = "disabled"


class DependencyStatus(ContractModel):
    name: str
    state: DependencyState
    latency_ms: float | None = None


class Readiness(ContractModel):
    status: str = Field(description="`ready` si toutes les dépendances requises répondent, sinon `degraded`")
    service: str
    version: str
    dependencies: list[DependencyStatus]
