"""Ordres soumis à revue et envoi fiable au simulateur (§ 7).

La commande porte l'état métier, la ligne d'envoi l'état technique (tentatives, échéance, dernière erreur).
"""

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class CommandState(StrEnum):
    AWAITING_REVIEW = "awaiting_review"
    REJECTED = "rejected"
    DISPATCHING = "dispatching"
    DISPATCHED = "dispatched"
    DISPATCH_FAILED = "dispatch_failed"


class CommandDecision(StrEnum):
    APPROVE = "approve"
    REJECT = "reject"
    RETRY = "retry"


class DispatchStatus(StrEnum):
    QUEUED = "queued"
    IN_FLIGHT = "in_flight"
    DONE = "done"
    FAILED = "failed"


class DispatchFailure(StrEnum):
    DEADLINE_PASSED = "deadline_passed"
    ATTEMPTS_EXHAUSTED = "attempts_exhausted"
    MANEUVER_REJECTED = "maneuver_rejected"
    MISSION_ENDED = "mission_ended"
    ORDER_NO_LONGER_VALID = "order_no_longer_valid"


STATES_ACCEPTING_DECISION: dict[CommandDecision, CommandState] = {
    CommandDecision.APPROVE: CommandState.AWAITING_REVIEW,
    CommandDecision.REJECT: CommandState.AWAITING_REVIEW,
    CommandDecision.RETRY: CommandState.DISPATCH_FAILED,
}

RETRY_BASE_DELAY_S = 0.5
RETRY_MAX_DELAY_S = 4.0


def retry_delay_s(attempts: int) -> float:
    """Attente croissante entre deux tentatives : 1 s, 2 s, puis 4 s au plus."""
    return min(RETRY_BASE_DELAY_S * float(2**attempts), RETRY_MAX_DELAY_S)


@dataclass(frozen=True, slots=True)
class Command:
    id: str
    mission_id: str
    text: str
    maneuver: dict[str, Any]
    state: CommandState
    submitted_by: str
    parent_id: str | None = None
    decided_by: str | None = None
    last_error: str | None = None

    @property
    def text_en(self) -> str:
        return str(self.maneuver["en"])

    @property
    def text_fr(self) -> str:
        return str(self.maneuver["fr"])


@dataclass(frozen=True, slots=True)
class Dispatch:
    """Ligne d'envoi prise par le répartiteur (`in_flight`)."""

    command_id: str
    mission_id: str
    text: str
    maneuver: dict[str, Any]
    attempts: int
    expired: bool
