"""Journal en mémoire pour le mode `fake` : même contrat que PostgreSQL, sans chaînage de hachage."""

from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Any

from hannibal_api.domain.audit import AuditEntry, AuditRecord, ChainVerification, MissionOutcome
from hannibal_api.domain.commands import Command, CommandDecision, CommandState, Dispatch, DispatchStatus


class InMemoryMissionJournal:
    def __init__(self) -> None:
        self.phase_by_mission: dict[str, str] = {}
        self.audit: list[AuditRecord] = []
        self.facts: list[dict[str, Any]] = []

    async def mission_started(
        self, mission_id: str, scenario_id: str, player_ship: str, owner_id: str, entry: AuditEntry
    ) -> None:
        self.phase_by_mission[mission_id] = "running"
        await self.record(entry)

    async def mission_finished(
        self, mission_id: str, outcome: MissionOutcome, debrief: dict[str, Any] | None, entry: AuditEntry
    ) -> None:
        self.phase_by_mission[mission_id] = outcome.value
        await self.record(entry)

    async def record(self, entry: AuditEntry) -> None:
        if entry.fact is not None:
            self.facts.append({"type": entry.fact.value, "subject": entry.mission_id, "data": entry.payload})
        self.audit.append(
            AuditRecord(
                seq=len(self.audit) + 1,
                at=datetime.now(UTC),
                actor_id=entry.actor_id,
                mission_id=entry.mission_id,
                command_id=entry.command_id,
                event=entry.event.value,
                payload=entry.payload,
            )
        )

    async def interrupt_unfinished(self) -> list[str]:
        return []

    async def read(self, mission_id: str | None, after_seq: int, limit: int) -> list[AuditRecord]:
        selected = [
            record
            for record in self.audit
            if record.seq > after_seq and (mission_id is None or record.mission_id == mission_id)
        ]
        return selected[:limit]

    async def verify(self) -> ChainVerification:
        head = self.audit[-1].seq if self.audit else None
        return ChainVerification(checked_events=len(self.audit), first_broken_seq=None, head_seq=head)


@dataclass(slots=True)
class _DispatchRow:
    status: DispatchStatus
    attempts: int
    next_attempt_at: float
    deadline_at: float
    queued_order: int


class InMemoryCommandStore:
    """Même contrat que `PostgresCommandStore` ; l'audit va dans le journal en mémoire."""

    def __init__(self, journal: InMemoryMissionJournal, clock: Callable[[], float]) -> None:
        self._journal = journal
        self._clock = clock
        self.commands_by_id: dict[str, Command] = {}
        self.dispatches_by_command: dict[str, _DispatchRow] = {}
        self._queued_count = 0

    async def create(self, command: Command, entry: AuditEntry) -> None:
        self.commands_by_id[command.id] = command
        await self._journal.record(entry)

    async def get(self, command_id: str) -> Command | None:
        return self.commands_by_id.get(command_id)

    async def decide(
        self,
        command_id: str,
        expected: CommandState,
        decision: CommandDecision,
        actor_id: str,
        validity_s: float,
        entry: AuditEntry,
    ) -> Command | None:
        command = self.commands_by_id.get(command_id)
        if command is None or command.state is not expected:
            return None
        now = self._clock()
        if decision is CommandDecision.REJECT:
            new_state = CommandState.REJECTED
        elif decision is CommandDecision.APPROVE:
            new_state = CommandState.DISPATCHING
            self._queue(command_id, deadline_at=now + validity_s)
        else:
            row = self.dispatches_by_command[command_id]
            if row.deadline_at <= now:
                return None
            new_state = CommandState.DISPATCHING
            self._queue(command_id, deadline_at=row.deadline_at)
        decided = replace(command, state=new_state, decided_by=actor_id, last_error=None)
        self.commands_by_id[command_id] = decided
        await self._journal.record(entry)
        return decided

    def _queue(self, command_id: str, deadline_at: float) -> None:
        self._queued_count += 1
        self.dispatches_by_command[command_id] = _DispatchRow(
            DispatchStatus.QUEUED, 0, self._clock(), deadline_at, self._queued_count
        )

    def _dispatch(self, command_id: str, row: _DispatchRow) -> Dispatch:
        command = self.commands_by_id[command_id]
        return Dispatch(
            command_id,
            command.mission_id,
            command.text,
            command.maneuver,
            row.attempts,
            row.deadline_at <= self._clock(),
        )

    async def claim_next(self) -> Dispatch | None:
        now = self._clock()
        ready = [
            (row.queued_order, command_id, row)
            for command_id, row in self.dispatches_by_command.items()
            if row.status is DispatchStatus.QUEUED and row.next_attempt_at <= now
        ]
        if not ready:
            return None
        _, command_id, row = min(ready, key=lambda item: item[0])
        row.status = DispatchStatus.IN_FLIGHT
        row.attempts += 1
        return self._dispatch(command_id, row)

    async def mark_dispatched(self, command_id: str, entry: AuditEntry) -> None:
        self.dispatches_by_command[command_id].status = DispatchStatus.DONE
        self.commands_by_id[command_id] = replace(
            self.commands_by_id[command_id], state=CommandState.DISPATCHED
        )
        await self._journal.record(entry)

    async def retry_later(self, command_id: str, delay_s: float, error: str, entry: AuditEntry) -> None:
        row = self.dispatches_by_command[command_id]
        row.status = DispatchStatus.QUEUED
        row.next_attempt_at = self._clock() + delay_s
        self.commands_by_id[command_id] = replace(self.commands_by_id[command_id], last_error=error)
        await self._journal.record(entry)

    async def mark_failed(self, command_id: str, error: str, entry: AuditEntry) -> None:
        self.dispatches_by_command[command_id].status = DispatchStatus.FAILED
        self.commands_by_id[command_id] = replace(
            self.commands_by_id[command_id], state=CommandState.DISPATCH_FAILED, last_error=error
        )
        await self._journal.record(entry)

    async def in_flight(self) -> list[Dispatch]:
        return [
            self._dispatch(command_id, row)
            for command_id, row in self.dispatches_by_command.items()
            if row.status is DispatchStatus.IN_FLIGHT
        ]

    async def requeue(self, command_id: str) -> None:
        self.dispatches_by_command[command_id].status = DispatchStatus.QUEUED
