"""Routes de l'assistant de doctrine (architecture 1.1.0 § 7). Le back-office a vérifié `doctrine:ask`."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query

from hannibal_api.application.doctrine import ExplainCommand, QueryDoctrine, SearchGlossary
from hannibal_api.presentation.missions import ERROR_RESPONSES, AuthenticatedUser
from hannibal_contracts.doctrine import (
    CommandExplanation,
    DoctrineAnswer,
    DoctrineQuestion,
    GlossaryResult,
    Publications,
)
from hannibal_platform.internal_auth import require_internal_token
from hannibal_platform.settings import BaseServiceSettings

DOCTRINE_RESPONSES = {**ERROR_RESPONSES, 429: ERROR_RESPONSES[403]}

UserPermissions = Annotated[
    str,
    Header(
        alias="X-Hx-Permissions",
        description="Permissions de la session, posées par le back-office (séparées par des virgules)",
    ),
]


def permission_set(header: str) -> frozenset[str]:
    return frozenset(p.strip() for p in header.split(",") if p.strip())


def doctrine_router(
    query_doctrine: QueryDoctrine,
    search_glossary: SearchGlossary,
    explain_command: ExplainCommand,
    settings: BaseServiceSettings,
) -> APIRouter:
    router = APIRouter(
        prefix="/v1", tags=["doctrine"], dependencies=[Depends(require_internal_token(settings))]
    )

    @router.post("/doctrine/questions", response_model=DoctrineAnswer, responses=DOCTRINE_RESPONSES)
    async def ask_doctrine(
        body: DoctrineQuestion, user: AuthenticatedUser = "local", permissions: UserPermissions = ""
    ) -> DoctrineAnswer:
        return await query_doctrine(body, actor_id=user, permissions=permission_set(permissions))

    @router.get("/doctrine/publications", response_model=Publications, responses=ERROR_RESPONSES)
    async def list_publications(permissions: UserPermissions = "") -> Publications:
        return Publications(
            publications=await query_doctrine.allowed_publications(permission_set(permissions))
        )

    @router.get("/glossary", response_model=GlossaryResult, responses=ERROR_RESPONSES)
    async def search_terms(q: Annotated[str, Query(min_length=1, max_length=100)]) -> GlossaryResult:
        return await search_glossary(q)

    @router.post(
        "/commands/{command_id}/explanation", response_model=CommandExplanation, responses=DOCTRINE_RESPONSES
    )
    async def explain_order(command_id: UUID) -> CommandExplanation:
        return await explain_command(str(command_id))

    return router
