"""Handlers `QueryDoctrine`, `SearchGlossary`, `ExplainCommand` (architecture 1.1.0 § 7).

Les publications classifiées ne sont cherchées qu'avec la permission `doctrine:classified`. Le GPU est
partagé : une question à la fois, deux en attente au plus, sinon `429 doctrine_busy`.
"""

import asyncio
import uuid
from collections.abc import AsyncIterator, Collection
from contextlib import asynccontextmanager

from hannibal_api.application.commands import Commands
from hannibal_api.application.missions import Busy, Forbidden
from hannibal_api.application.ports import DoctrinePort, DoctrineTraceStore
from hannibal_api.domain.audit import AuditEntry, AuditEvent
from hannibal_api.domain.doctrine import CLASSIFIED_PERMISSION, DoctrineTrace, order_parameters
from hannibal_contracts.doctrine import (
    AnswerStatus,
    AskRequest,
    CommandExplanation,
    DoctrineAnswer,
    DoctrineQuestion,
    ExplainRequest,
    GlossaryResult,
)
from hannibal_platform.logging import get_logger

log = get_logger(__name__)


class DoctrineBusy(Busy):
    code = "doctrine_busy"
    message = "L'assistant de doctrine est occupé, réessayez dans un instant."


class PublicationNotAllowed(Forbidden):
    code = "publication_not_allowed"
    message = "Publication inconnue ou non autorisée pour ce rôle."


class GpuGate:
    def __init__(self, *, active: int, waiting: int, wait_s: float) -> None:
        self._slots = asyncio.Semaphore(active)
        self._waiting = 0
        self._max_waiting = waiting
        self._wait_s = wait_s

    @asynccontextmanager
    async def slot(self) -> AsyncIterator[None]:
        if self._slots.locked() and self._waiting >= self._max_waiting:
            raise DoctrineBusy(reason="queue_full")
        self._waiting += 1
        try:
            await asyncio.wait_for(self._slots.acquire(), self._wait_s)
        except TimeoutError:
            raise DoctrineBusy(reason="wait_timeout") from None
        finally:
            self._waiting -= 1
        try:
            yield
        finally:
            self._slots.release()


class QueryDoctrine:
    def __init__(self, doctrine: DoctrinePort, traces: DoctrineTraceStore, gate: GpuGate) -> None:
        self._doctrine = doctrine
        self._traces = traces
        self._gate = gate

    async def allowed_publications(self, permissions: Collection[str]) -> list[str]:
        return await self._doctrine.publications(include_classified=CLASSIFIED_PERMISSION in permissions)

    async def __call__(
        self, question: DoctrineQuestion, *, actor_id: str, permissions: Collection[str]
    ) -> DoctrineAnswer:
        classified = CLASSIFIED_PERMISSION in permissions
        if question.publication and question.publication not in await self.allowed_publications(permissions):
            raise PublicationNotAllowed(publication=question.publication)
        request = AskRequest(
            question=question.question,
            language=question.language,
            publications=[question.publication] if question.publication else [],
            include_classified=classified,
        )
        async with self._gate.slot():
            response = await self._doctrine.ask(request)
        trace_id = str(uuid.uuid4())
        answered = response.status is AnswerStatus.ANSWERED
        await self._traces.save(
            DoctrineTrace(
                id=trace_id,
                actor_id=actor_id,
                question=question.question,
                language=question.language.value,
                publication=question.publication,
                status=response.status.value,
                refusal_reason=response.refusal_reason.value if response.refusal_reason else None,
                answer=response.answer,
                model=response.model,
                index_version=response.index_version,
                duration_ms=response.duration_ms,
                cited=[
                    {"number": c.number, "passage_id": c.passage_id, "publication": c.publication}
                    for c in response.citations
                ],
                thresholds=response.thresholds,
            ),
            AuditEntry(
                AuditEvent.DOCTRINE_ANSWERED if answered else AuditEvent.DOCTRINE_REFUSED,
                actor_id,
                None,
                {
                    "trace_id": trace_id,
                    "publication": question.publication,
                    "refusal_reason": None if answered else response.refusal_reason,
                    "citations": len(response.citations),
                    "index_version": response.index_version,
                },
            ),
        )
        log.info(
            "doctrine_question", trace_id=trace_id, status=response.status.value, ms=response.duration_ms
        )
        return DoctrineAnswer(**response.model_dump(), trace_id=uuid.UUID(trace_id))


class SearchGlossary:
    def __init__(self, doctrine: DoctrinePort) -> None:
        self._doctrine = doctrine

    async def __call__(self, query: str) -> GlossaryResult:
        return await self._doctrine.glossary(query.strip().lower())


class ExplainCommand:
    """Explication d'un ordre déjà interprété : le modèle reformule, les valeurs décodées font foi."""

    def __init__(self, doctrine: DoctrinePort, commands: Commands, gate: GpuGate) -> None:
        self._doctrine = doctrine
        self._commands = commands
        self._gate = gate

    async def __call__(self, command_id: str) -> CommandExplanation:
        command = await self._commands.read(command_id)
        request = ExplainRequest(
            message=command.text,
            meaning_en=command.text_en,
            meaning_fr=command.text_fr,
            parameters=order_parameters(command.maneuver.get("orders") or []),
        )
        async with self._gate.slot():
            explanation = await self._doctrine.explain(request)
        return CommandExplanation(**explanation.model_dump(), command_id=uuid.UUID(command_id))
