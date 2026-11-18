"""Contrats de session du back-office (ADR 0007) : connexion par compte local, cookie de session."""

from datetime import datetime

from pydantic import Field

from hannibal_contracts.base import ContractModel


class SignIn(ContractModel):
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=200)


class SessionView(ContractModel):
    username: str
    role: str = Field(description="`operator`, `supervisor` ou `admin`")
    permissions: list[str] = Field(description="Permissions du rôle, ex. `command:decide`")
    expires_at: datetime = Field(description="Fin de la session sans activité ; prolongée à chaque requête")
