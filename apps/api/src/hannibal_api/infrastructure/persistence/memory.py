"""Journal en mémoire pour le mode `fake` : même contrat que PostgreSQL, sans chaînage de hachage."""

from datetime import UTC, datetime
from typing import Any

from hannibal_api.domain.audit import AuditEntry, AuditRecord, ChainVerification, MissionOutcome


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
                command_id=None,
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
