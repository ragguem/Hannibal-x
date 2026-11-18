"""Contrats du registre métier (§ 11) : lecture paginée et état de la chaîne de hachage."""

from datetime import datetime
from typing import Any

from pydantic import Field

from hannibal_contracts.base import ContractModel


class AuditEventView(ContractModel):
    seq: int = Field(description="Numéro d'ordre attribué par la base, sans trou")
    at: datetime
    actor_id: str | None = Field(
        description="Utilisateur à l'origine de l'événement ; absent pour le système"
    )
    mission_id: str | None = None
    command_id: str | None = None
    event: str
    payload: dict[str, Any]


class AuditPage(ContractModel):
    events: list[AuditEventView]
    next_after_seq: int | None = Field(
        description="À passer en `after_seq` pour la page suivante ; absent à la fin"
    )


class AuditIntegrity(ContractModel):
    intact: bool
    checked_events: int
    first_broken_seq: int | None = Field(description="Première ligne modifiée, insérée ou retirée après coup")
    head_seq: int | None = None
