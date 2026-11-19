"""Adaptateur PostgreSQL de `CommandStore` : commandes, registre des envois et audit dans la même transaction.

Les échéances sont calculées par l'horloge de la base (`now()`), seule commune à toutes les instances.
"""

from collections.abc import Sequence
from datetime import timedelta
from typing import Any

from sqlalchemy import func, insert, select, update
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from hannibal_api.domain.audit import AuditEntry
from hannibal_api.domain.commands import (
    Command,
    CommandDecision,
    CommandSource,
    CommandState,
    Dispatch,
    DispatchStatus,
)
from hannibal_api.infrastructure.persistence.journal import transaction, write_audit
from hannibal_api.infrastructure.persistence.tables import command_dispatches, commands


def _to_command(row: Any) -> Command:
    return Command(
        id=str(row["id"]),
        mission_id=str(row["mission_id"]),
        text=row["text"],
        maneuver=row["maneuver"],
        state=CommandState(row["state"]),
        submitted_by=row["submitted_by"],
        parent_id=None if row["parent_id"] is None else str(row["parent_id"]),
        decided_by=row["decided_by"],
        last_error=row["last_error"],
        source=CommandSource(row["source"]),
    )


_DISPATCH_COLUMNS = (
    commands.c.id,
    commands.c.mission_id,
    commands.c.text,
    commands.c.maneuver,
    command_dispatches.c.attempts,
    (command_dispatches.c.deadline_at <= func.now()).label("expired"),
)


def _to_dispatch(row: Any) -> Dispatch:
    return Dispatch(
        command_id=str(row["id"]),
        mission_id=str(row["mission_id"]),
        text=row["text"],
        maneuver=row["maneuver"],
        attempts=row["attempts"],
        expired=bool(row["expired"]),
    )


class PostgresCommandStore:
    def __init__(self, engine: AsyncEngine | None) -> None:
        self._engine = engine

    async def create(self, command: Command, entries: Sequence[AuditEntry]) -> None:
        async with transaction(self._engine) as connection:
            await connection.execute(
                insert(commands).values(
                    id=command.id,
                    mission_id=command.mission_id,
                    parent_id=command.parent_id,
                    source=command.source.value,
                    text=command.text,
                    maneuver=command.maneuver,
                    state=command.state.value,
                    submitted_by=command.submitted_by,
                )
            )
            for entry in entries:
                await write_audit(connection, entry)

    async def get(self, command_id: str) -> Command | None:
        async with transaction(self._engine) as connection:
            row = (
                (await connection.execute(select(commands).where(commands.c.id == command_id)))
                .mappings()
                .first()
            )
        return None if row is None else _to_command(row)

    async def decide(
        self,
        command_id: str,
        expected: CommandState,
        decision: CommandDecision,
        actor_id: str,
        validity_s: float,
        entry: AuditEntry,
    ) -> Command | None:
        async with transaction(self._engine) as connection:
            locked = (
                await connection.execute(
                    select(commands.c.state).where(commands.c.id == command_id).with_for_update()
                )
            ).scalar_one_or_none()
            if locked != expected.value:
                return None
            if decision is CommandDecision.REJECT:
                new_state = CommandState.REJECTED
            elif decision is CommandDecision.APPROVE:
                new_state = CommandState.DISPATCHING
                await connection.execute(
                    insert(command_dispatches).values(
                        command_id=command_id,
                        status=DispatchStatus.QUEUED.value,
                        deadline_at=func.now() + timedelta(seconds=validity_s),
                    )
                )
            else:
                requeued = await connection.execute(
                    update(command_dispatches)
                    .where(
                        command_dispatches.c.command_id == command_id,
                        command_dispatches.c.deadline_at > func.now(),
                    )
                    .values(
                        status=DispatchStatus.QUEUED.value,
                        attempts=0,
                        next_attempt_at=func.now(),
                        queued_at=func.clock_timestamp(),
                        updated_at=func.now(),
                    )
                )
                if requeued.rowcount == 0:
                    return None
                new_state = CommandState.DISPATCHING
            row = (
                (
                    await connection.execute(
                        update(commands)
                        .where(commands.c.id == command_id)
                        .values(
                            state=new_state.value, decided_by=actor_id, decided_at=func.now(), last_error=None
                        )
                        .returning(*commands.c)
                    )
                )
                .mappings()
                .one()
            )
            await write_audit(connection, entry)
        return _to_command(row)

    async def claim_next(self) -> Dispatch | None:
        async with transaction(self._engine) as connection:
            command_id = (
                await connection.execute(
                    select(command_dispatches.c.command_id)
                    .where(
                        command_dispatches.c.status == DispatchStatus.QUEUED.value,
                        command_dispatches.c.next_attempt_at <= func.now(),
                    )
                    .order_by(command_dispatches.c.queued_at)
                    .limit(1)
                    .with_for_update(skip_locked=True)
                )
            ).scalar_one_or_none()
            if command_id is None:
                return None
            await connection.execute(
                update(command_dispatches)
                .where(command_dispatches.c.command_id == command_id)
                .values(
                    status=DispatchStatus.IN_FLIGHT.value,
                    attempts=command_dispatches.c.attempts + 1,
                    last_attempt_at=func.now(),
                    updated_at=func.now(),
                )
            )
            return await self._read_dispatch(connection, str(command_id))

    @staticmethod
    async def _read_dispatch(connection: AsyncConnection, command_id: str) -> Dispatch:
        row = (
            (
                await connection.execute(
                    select(*_DISPATCH_COLUMNS)
                    .join(command_dispatches, command_dispatches.c.command_id == commands.c.id)
                    .where(commands.c.id == command_id)
                )
            )
            .mappings()
            .one()
        )
        return _to_dispatch(row)

    async def _finish(
        self,
        command_id: str,
        status: DispatchStatus,
        command_values: dict[str, Any],
        error: str | None,
        entry: AuditEntry,
    ) -> None:
        async with transaction(self._engine) as connection:
            await connection.execute(
                update(command_dispatches)
                .where(command_dispatches.c.command_id == command_id)
                .values(status=status.value, last_error=error, updated_at=func.now())
            )
            await connection.execute(
                update(commands).where(commands.c.id == command_id).values(**command_values)
            )
            await write_audit(connection, entry)

    async def mark_dispatched(self, command_id: str, entry: AuditEntry) -> None:
        await self._finish(
            command_id,
            DispatchStatus.DONE,
            {"state": CommandState.DISPATCHED.value, "dispatched_at": func.now()},
            None,
            entry,
        )

    async def mark_failed(self, command_id: str, error: str, entry: AuditEntry) -> None:
        await self._finish(
            command_id,
            DispatchStatus.FAILED,
            {"state": CommandState.DISPATCH_FAILED.value, "last_error": error},
            error,
            entry,
        )

    async def retry_later(self, command_id: str, delay_s: float, error: str, entry: AuditEntry) -> None:
        async with transaction(self._engine) as connection:
            await connection.execute(
                update(command_dispatches)
                .where(command_dispatches.c.command_id == command_id)
                .values(
                    status=DispatchStatus.QUEUED.value,
                    next_attempt_at=func.now() + timedelta(seconds=delay_s),
                    last_error=error,
                    updated_at=func.now(),
                )
            )
            await connection.execute(
                update(commands).where(commands.c.id == command_id).values(last_error=error)
            )
            await write_audit(connection, entry)

    async def in_flight(self) -> list[Dispatch]:
        async with transaction(self._engine) as connection:
            rows = (
                (
                    await connection.execute(
                        select(*_DISPATCH_COLUMNS)
                        .join(command_dispatches, command_dispatches.c.command_id == commands.c.id)
                        .where(command_dispatches.c.status == DispatchStatus.IN_FLIGHT.value)
                        .order_by(command_dispatches.c.queued_at)
                    )
                )
                .mappings()
                .all()
            )
        return [_to_dispatch(row) for row in rows]

    async def requeue(self, command_id: str) -> None:
        async with transaction(self._engine) as connection:
            await connection.execute(
                update(command_dispatches)
                .where(command_dispatches.c.command_id == command_id)
                .values(status=DispatchStatus.QUEUED.value, updated_at=func.now())
            )
