"""Adaptateurs PostgreSQL de `MissionJournal` et `AuditReader`.

Dans chaque transaction, l'insert d'audit est la dernière écriture : le déclencheur de chaînage tient un
verrou consultatif jusqu'à la validation (§ 23).
"""

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from sqlalchemy import func, insert, select, text, update
from sqlalchemy.exc import DBAPIError, IntegrityError, InterfaceError, OperationalError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from hannibal_api.domain.audit import AuditEntry, AuditEvent, AuditRecord, ChainVerification, MissionOutcome
from hannibal_api.infrastructure.persistence.tables import audit_events, integration_outbox, missions
from hannibal_platform.errors import Conflict, DatabaseUnavailable

CLOUDEVENTS_SPEC_VERSION = "1.0"
FACT_SOURCE = "/hannibal-x/api"


class MissionAlreadyRecorded(Conflict):
    code = "mission_running"
    message = "Une mission est déjà en cours."


@asynccontextmanager
async def transaction(engine: AsyncEngine | None) -> AsyncIterator[AsyncConnection]:
    if engine is None:
        raise DatabaseUnavailable("HX_API_DATABASE_URL non défini")
    try:
        async with engine.begin() as connection:
            yield connection
    except IntegrityError:
        raise
    except (OperationalError, InterfaceError, OSError, DBAPIError) as error:
        raise DatabaseUnavailable(type(error).__name__) from error


async def write_audit(connection: AsyncConnection, entry: AuditEntry) -> None:
    if entry.fact is not None:
        await connection.execute(
            insert(integration_outbox).values(
                id=str(uuid.uuid4()),
                specversion=CLOUDEVENTS_SPEC_VERSION,
                type=entry.fact.value,
                source=FACT_SOURCE,
                subject=entry.mission_id,
                data={"actor_id": entry.actor_id, "mission_id": entry.mission_id, **entry.payload},
            )
        )
    await connection.execute(
        insert(audit_events).values(
            actor_id=entry.actor_id,
            mission_id=entry.mission_id,
            command_id=entry.command_id,
            event=entry.event.value,
            payload=entry.payload,
        )
    )


class PostgresMissionJournal:
    def __init__(self, engine: AsyncEngine | None) -> None:
        self._engine = engine

    async def mission_started(
        self, mission_id: str, scenario_id: str, player_ship: str, owner_id: str, entry: AuditEntry
    ) -> None:
        try:
            async with transaction(self._engine) as connection:
                await connection.execute(
                    insert(missions).values(
                        id=mission_id,
                        scenario_id=scenario_id,
                        player_ship=player_ship,
                        phase="running",
                        owner_id=owner_id,
                    )
                )
                await write_audit(connection, entry)
        except IntegrityError as error:
            raise MissionAlreadyRecorded(mission_id=mission_id) from error

    async def mission_finished(
        self, mission_id: str, outcome: MissionOutcome, debrief: dict[str, Any] | None, entry: AuditEntry
    ) -> None:
        async with transaction(self._engine) as connection:
            await connection.execute(
                update(missions)
                .where(missions.c.id == mission_id)
                .values(phase=outcome.value, finished_at=func.now(), debrief=debrief)
            )
            await write_audit(connection, entry)

    async def record(self, entry: AuditEntry) -> None:
        async with transaction(self._engine) as connection:
            await write_audit(connection, entry)

    async def interrupt_unfinished(self) -> list[str]:
        async with transaction(self._engine) as connection:
            rows = await connection.execute(
                update(missions)
                .where(missions.c.phase == "running")
                .values(phase=MissionOutcome.INTERRUPTED.value, finished_at=func.now())
                .returning(missions.c.id)
            )
            interrupted = [str(mission_id) for (mission_id,) in rows]
            for mission_id in interrupted:
                await write_audit(
                    connection,
                    AuditEntry(
                        AuditEvent.MISSION_FINISHED,
                        None,
                        mission_id,
                        {"outcome": MissionOutcome.INTERRUPTED.value, "reason": "api_restarted"},
                    ),
                )
        return interrupted


class PostgresAuditReader:
    def __init__(self, engine: AsyncEngine | None) -> None:
        self._engine = engine

    async def read(self, mission_id: str | None, after_seq: int, limit: int) -> list[AuditRecord]:
        query = (
            select(audit_events)
            .where(audit_events.c.seq > after_seq)
            .order_by(audit_events.c.seq)
            .limit(limit)
        )
        if mission_id is not None:
            query = query.where(audit_events.c.mission_id == mission_id)
        async with transaction(self._engine) as connection:
            rows = (await connection.execute(query)).mappings().all()
        return [
            AuditRecord(
                seq=row["seq"],
                at=row["at"],
                actor_id=row["actor_id"],
                mission_id=None if row["mission_id"] is None else str(row["mission_id"]),
                command_id=None if row["command_id"] is None else str(row["command_id"]),
                event=row["event"],
                payload=row["payload"],
            )
            for row in rows
        ]

    async def verify(self) -> ChainVerification:
        async with transaction(self._engine) as connection:
            checked, first_broken = (
                await connection.execute(
                    text("SELECT checked_events, first_broken_seq FROM ops.verify_audit_chain()")
                )
            ).one()
            head = (await connection.execute(text("SELECT seq FROM ops.audit_head()"))).scalar_one_or_none()
        return ChainVerification(checked_events=checked, first_broken_seq=first_broken, head_seq=head)
