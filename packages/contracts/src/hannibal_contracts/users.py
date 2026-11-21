"""Gestion des comptes par le back-office (Lot 7.2), réservée à la permission `user:manage`."""

from datetime import datetime
from uuid import UUID

from pydantic import Field

from hannibal_contracts.base import ContractModel


class UserView(ContractModel):
    id: UUID
    username: str
    role: str = Field(description="`operator`, `supervisor` ou `admin`")
    created_at: datetime
    disabled_at: datetime | None = Field(
        description="Compte désactivé : plus de connexion, sessions révoquées"
    )
    password_changed_at: datetime | None = Field(
        description="Nul tant que l'utilisateur garde le mot de passe provisoire donné par un administrateur"
    )


class UserList(ContractModel):
    users: list[UserView] = Field(description="Tous les comptes, par nom")


class RoleView(ContractModel):
    code: str
    label: str
    permissions: list[str]


class RoleList(ContractModel):
    roles: list[RoleView]


class CreateUser(ContractModel):
    username: str = Field(pattern=r"^[a-z0-9._-]{3,32}$")
    role: str


class ChangeUserRole(ContractModel):
    role: str


class IssuedPassword(ContractModel):
    user: UserView
    temporary_password: str = Field(description="Affiché une seule fois, à transmettre à l'utilisateur")


class ChangePassword(ContractModel):
    current_password: str = Field(min_length=1, max_length=200)
    new_password: str = Field(min_length=12, max_length=200)
