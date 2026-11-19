from dataclasses import asdict

from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncEngine

from hannibal_api.domain.audit import AuditEntry
from hannibal_api.domain.doctrine import DoctrineTrace
from hannibal_api.infrastructure.persistence.journal import transaction, write_audit
from hannibal_api.infrastructure.persistence.tables import doctrine_traces


class PostgresDoctrineTraceStore:
    def __init__(self, engine: AsyncEngine | None) -> None:
        self._engine = engine

    async def save(self, trace: DoctrineTrace, entry: AuditEntry) -> None:
        async with transaction(self._engine) as connection:
            await connection.execute(insert(doctrine_traces).values(**asdict(trace)))
            await write_audit(connection, entry)
