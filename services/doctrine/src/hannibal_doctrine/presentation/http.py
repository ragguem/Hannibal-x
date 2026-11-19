from typing import Annotated

from fastapi import APIRouter, Depends, Query

from hannibal_contracts.doctrine import (
    AnswerStatus,
    AskRequest,
    AskResponse,
    Citation,
    ExplainRequest,
    Explanation,
    GlossaryEntry,
    GlossaryResult,
    Publications,
    TermProposal,
    TermSuggestion,
)
from hannibal_doctrine.application.ask import DoctrineResult
from hannibal_doctrine.application.extracts import Extract
from hannibal_doctrine.application.ports import DependencyDown, SearchScope
from hannibal_doctrine.application.use_cases import DoctrineUseCases
from hannibal_platform.errors import DependencyUnavailable
from hannibal_platform.internal_auth import require_internal_token
from hannibal_platform.settings import BaseServiceSettings


def to_citation(extract: Extract) -> Citation:
    p = extract.passage
    return Citation(
        number=extract.number,
        passage_id=p.id,
        publication=p.publication,
        edition=p.edition,
        chapter=p.chapter,
        section=p.section,
        article=p.article,
        title=p.title,
        page=p.page,
        pdf_page=p.pdf_page,
        text=p.text,
        table_row=extract.table_row,
    )


def to_ask_response(result: DoctrineResult) -> AskResponse:
    return AskResponse(
        status=AnswerStatus.REFUSED if result.refusal else AnswerStatus.ANSWERED,
        answer=result.answer,
        refusal_reason=result.refusal.reason if result.refusal else None,
        refusal_detail=result.refusal.detail if result.refusal else None,
        citations=[to_citation(e) for e in result.cited],
        unknown_terms=result.advice.unknown,
        suggestions=[
            TermSuggestion(
                unknown=s["inconnu"],
                proposals=[
                    TermProposal(term=p["terme"], en=p["en"], fr=p["fr"] or None) for p in s["propositions"]
                ],
            )
            for s in result.advice.suggestions
        ],
        query_en=result.query_en or None,
        model=result.model,
        index_version=result.index_version,
        thresholds=result.thresholds,
        second_try=result.second_try,
        duration_ms=result.duration_ms,
    )


def doctrine_router(use_cases: DoctrineUseCases, settings: BaseServiceSettings) -> APIRouter:
    router = APIRouter(dependencies=[Depends(require_internal_token(settings))])

    @router.post("/ask", response_model=AskResponse)
    async def ask_doctrine(request: AskRequest) -> AskResponse:
        try:
            result = await use_cases.ask(
                request.question, request.language, request.publications, request.include_classified
            )
        except DependencyDown as error:
            raise DependencyUnavailable(error.dependency, str(error)) from error
        return to_ask_response(result)

    @router.get("/glossary", response_model=GlossaryResult)
    async def search_glossary(q: Annotated[str, Query(max_length=100)] = "") -> GlossaryResult:
        try:
            terms = await use_cases.lookup_glossary(q)
        except DependencyDown as error:
            raise DependencyUnavailable(error.dependency, str(error)) from error
        return GlossaryResult(
            query=q,
            entries=[
                GlossaryEntry(
                    en=t.en,
                    fr=t.fr,
                    sense=t.sense,
                    abbreviation=t.abbreviation,
                    definition_en=t.definition_en,
                    definition_fr=t.definition_fr,
                    source=t.source,
                    page=t.page,
                    status=t.status,
                )
                for t in terms
            ],
        )

    @router.get("/publications", response_model=Publications)
    async def list_publications(include_classified: bool = False) -> Publications:
        scope = SearchScope(excluded=() if include_classified else use_cases.classified_publications)
        try:
            return Publications(publications=await use_cases.index.publications(scope))
        except DependencyDown as error:
            raise DependencyUnavailable(error.dependency, str(error)) from error

    @router.post("/explain", response_model=Explanation)
    async def explain_order(request: ExplainRequest) -> Explanation:
        result = await use_cases.explain_order(
            request.message, request.meaning_en, request.meaning_fr, request.parameters
        )
        return Explanation(
            explanation_en=result.explanation_en,
            explanation_fr=result.explanation_fr,
            source=result.source,
            citations=[to_citation(e) for e in result.cited],
            rejected_checks=result.rejected_checks,
            model=result.model,
            duration_ms=result.duration_ms,
        )

    return router
