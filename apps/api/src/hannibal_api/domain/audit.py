"""Registre métier (§ 11, § 23) : la base attribue le numéro d'ordre et calcule le chaînage."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any


class AuditEvent(StrEnum):
    MISSION_STARTED = "mission_started"
    MISSION_FINISHED = "mission_finished"
    APPROVED = "approved"
    REJECTED = "rejected"
    HELM = "helm"
    CONTACT_CLASSIFIED = "contact_classified"
    TRANSCRIBED = "transcribed"
    AWAITING_REVIEW = "awaiting_review"
    SIMULATOR_DISPATCHED = "simulator_dispatched"
    DISPATCH_RETRY = "dispatch_retry"
    DISPATCH_FAILED = "dispatch_failed"


class FactType(StrEnum):
    """Faits métier publiés dans `ops.integration_outbox` (enveloppe CloudEvents 1.0)."""

    MISSION_STARTED = "hx.mission.started.v1"
    MISSION_FINISHED = "hx.mission.finished.v1"
    COMMAND_APPROVED = "hx.command.approved.v1"
    COMMAND_REJECTED = "hx.command.rejected.v1"
    CONTACT_CLASSIFIED = "hx.contact.classified.v1"


class MissionOutcome(StrEnum):
    FINISHED = "finished"
    INTERRUPTED = "interrupted"


@dataclass(frozen=True, slots=True)
class AuditEntry:
    """Ce que l'API écrit ; `seq`, `at` et les hachages viennent de la base."""

    event: AuditEvent
    actor_id: str | None
    mission_id: str | None
    payload: dict[str, Any] = field(default_factory=dict)
    fact: FactType | None = None
    command_id: str | None = None


@dataclass(frozen=True, slots=True)
class AuditRecord:
    seq: int
    at: datetime
    actor_id: str | None
    mission_id: str | None
    command_id: str | None
    event: str
    payload: dict[str, Any]


@dataclass(frozen=True, slots=True)
class ChainVerification:
    checked_events: int
    first_broken_seq: int | None
    head_seq: int | None

    @property
    def intact(self) -> bool:
        return self.first_broken_seq is None
