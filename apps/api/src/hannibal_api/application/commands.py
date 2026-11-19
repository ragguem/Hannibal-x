"""Handlers `SubmitOrder` (mode `review`) et `DecideCommand` (§ 7).

`DecideCommand` ne parle pas au simulateur : il écrit la décision et l'intention d'envoi, puis réveille
le répartiteur.
"""

import uuid
from collections.abc import Callable, Sequence
from typing import Any

from hannibal_api.application.missions import Conflict, Missions, NotFound
from hannibal_api.application.ports import CommandStore
from hannibal_api.domain.audit import AuditEntry, AuditEvent, FactType
from hannibal_api.domain.commands import (
    STATES_ACCEPTING_DECISION,
    Command,
    CommandDecision,
    CommandSource,
    CommandState,
)
from hannibal_platform.logging import get_logger

log = get_logger(__name__)


class CommandNotFound(NotFound):
    code = "command_not_found"
    message = "Commande inconnue."


class DecisionNotAllowed(Conflict):
    code = "decision_not_allowed"
    message = "Cette décision n'est pas possible dans l'état actuel de la commande."


class CommandExpired(Conflict):
    code = "command_expired"
    message = "L'échéance de validité est passée : soumettre un nouvel ordre."


AUDIT_EVENT_BY_DECISION = {
    CommandDecision.APPROVE: AuditEvent.APPROVED,
    CommandDecision.REJECT: AuditEvent.REJECTED,
    CommandDecision.RETRY: AuditEvent.APPROVED,
}
FACT_BY_DECISION = {
    CommandDecision.APPROVE: FactType.COMMAND_APPROVED,
    CommandDecision.REJECT: FactType.COMMAND_REJECTED,
    CommandDecision.RETRY: None,
}


class Commands:
    def __init__(
        self,
        missions: Missions,
        store: CommandStore,
        wake_dispatcher: Callable[[], None],
        validity_s: float,
    ) -> None:
        self._missions = missions
        self._store = store
        self._wake_dispatcher = wake_dispatcher
        self._validity_s = validity_s

    async def submit_for_review(
        self,
        mission_id: str,
        text: str,
        *,
        actor_id: str,
        parent_id: str | None,
        source: CommandSource = CommandSource.KEYBOARD,
        command_id: str | None = None,
        preceding_entries: Sequence[AuditEntry] = (),
    ) -> tuple[dict[str, Any], Command | None]:
        """Interprète l'ordre et, s'il est valide, crée la commande `awaiting_review`.

        `preceding_entries` (la transcription d'un ordre vocal) est écrit dans la même transaction.
        """
        checked = self._missions.check_order(mission_id, text)
        if not checked["ok"]:
            return checked, None
        if parent_id is not None and await self._store.get(parent_id) is None:
            raise CommandNotFound(command_id=parent_id)
        command = Command(
            id=command_id or str(uuid.uuid4()),
            mission_id=mission_id,
            text=text,
            maneuver={key: checked[key] for key in ("to", "orders", "en", "fr")},
            state=CommandState.AWAITING_REVIEW,
            submitted_by=actor_id,
            parent_id=parent_id,
            source=source,
        )
        awaiting_review = AuditEntry(
            AuditEvent.AWAITING_REVIEW,
            actor_id,
            mission_id,
            {
                "source": source.value,
                "text_en": command.text_en,
                "text_fr": command.text_fr,
                "parent_id": parent_id,
            },
            command_id=command.id,
        )
        await self._store.create(command, [*preceding_entries, awaiting_review])
        return checked, command

    async def read(self, command_id: str) -> Command:
        command = await self._store.get(command_id)
        if command is None:
            raise CommandNotFound(command_id=command_id)
        return command

    async def decide(self, command_id: str, decision: CommandDecision, *, actor_id: str) -> Command:
        command = await self.read(command_id)
        expected = STATES_ACCEPTING_DECISION[decision]
        if command.state is not expected:
            raise DecisionNotAllowed(
                command_id=command_id, state=command.state.value, decision=decision.value
            )
        if decision is not CommandDecision.REJECT and not self._missions.is_active(command.mission_id):
            raise CommandExpired(command_id=command_id, reason="mission_ended")
        decided = await self._store.decide(
            command_id,
            expected,
            decision,
            actor_id,
            self._validity_s,
            AuditEntry(
                AUDIT_EVENT_BY_DECISION[decision],
                actor_id,
                command.mission_id,
                {"source": "review", "decision": decision.value, "text_en": command.text_en},
                FACT_BY_DECISION[decision],
                command_id=command_id,
            ),
        )
        if decided is None:
            if decision is CommandDecision.RETRY:
                raise CommandExpired(command_id=command_id)
            raise DecisionNotAllowed(command_id=command_id, decision=decision.value)
        if decided.state is CommandState.DISPATCHING:
            self._wake_dispatcher()
        log.info("command_decided", command_id=command_id, decision=decision.value, actor_id=actor_id)
        return decided
