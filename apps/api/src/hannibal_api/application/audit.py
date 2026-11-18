"""Handlers `ReadAudit` et `VerifyAudit` (§ 11)."""

from hannibal_api.application.ports import AuditReader
from hannibal_api.domain.audit import AuditRecord, ChainVerification

MAX_PAGE_SIZE = 500


class AuditTrail:
    def __init__(self, reader: AuditReader) -> None:
        self._reader = reader

    async def read(self, mission_id: str | None, after_seq: int, limit: int) -> list[AuditRecord]:
        return await self._reader.read(mission_id, max(after_seq, 0), min(max(limit, 1), MAX_PAGE_SIZE))

    async def verify(self) -> ChainVerification:
        return await self._reader.verify()
