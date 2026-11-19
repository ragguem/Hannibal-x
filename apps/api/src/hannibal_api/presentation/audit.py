from http import HTTPStatus
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response

from hannibal_api.application.audit import MAX_PAGE_SIZE, AuditTrail
from hannibal_api.application.voice_orders import VoiceOrders
from hannibal_api.presentation.missions import ERROR_RESPONSES
from hannibal_contracts.audit import AuditEventView, AuditIntegrity, AuditPage
from hannibal_platform.internal_auth import require_internal_token
from hannibal_platform.settings import BaseServiceSettings

DEFAULT_PAGE_SIZE = 100


def audit_router(trail: AuditTrail, voice_orders: VoiceOrders, settings: BaseServiceSettings) -> APIRouter:
    router = APIRouter(
        prefix="/v1", tags=["registre"], dependencies=[Depends(require_internal_token(settings))]
    )

    @router.get("/audit", response_model=AuditPage, responses=ERROR_RESPONSES)
    async def read_audit(
        mission_id: Annotated[UUID | None, Query()] = None,
        after_seq: Annotated[int, Query(ge=0)] = 0,
        limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = DEFAULT_PAGE_SIZE,
    ) -> AuditPage:
        records = await trail.read(None if mission_id is None else str(mission_id), after_seq, limit)
        return AuditPage(
            events=[
                AuditEventView(
                    seq=record.seq,
                    at=record.at,
                    actor_id=record.actor_id,
                    mission_id=record.mission_id,
                    command_id=record.command_id,
                    event=record.event,
                    payload=record.payload,
                )
                for record in records
            ],
            next_after_seq=records[-1].seq if len(records) == limit else None,
        )

    @router.get(
        "/audit/{command_id}/audio",
        response_class=Response,
        responses={HTTPStatus.OK: {"content": {"audio/wav": {}, "audio/webm": {}}}, **ERROR_RESPONSES},
        summary="Enregistrement d'un ordre vocal, même politique d'accès que ReadAudit",
    )
    async def read_recording(command_id: UUID) -> Response:
        recording = await voice_orders.read_recording(str(command_id))
        return Response(
            recording.content,
            media_type=recording.media_type,
            headers={"Cache-Control": "private, max-age=3600"},
        )

    @router.get("/audit/integrity", response_model=AuditIntegrity, responses=ERROR_RESPONSES)
    async def verify_audit() -> AuditIntegrity:
        verification = await trail.verify()
        return AuditIntegrity(
            intact=verification.intact,
            checked_events=verification.checked_events,
            first_broken_seq=verification.first_broken_seq,
            head_seq=verification.head_seq,
        )

    return router
