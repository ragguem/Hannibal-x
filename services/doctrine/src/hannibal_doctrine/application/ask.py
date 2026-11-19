"""`AskDoctrine` : reformuler, chercher, reclasser, couvrir, rédiger, valider les preuves, sinon refuser.

Repris de legacy/v2/scripts/hx2_service_c.py (`ask`, `_answer`) : second essai sur les meilleurs extraits
seulement, puis modèle de repli s'il est configuré, avant de refuser. Les termes inconnus sont signalés.
"""

import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

from hannibal_core.grounding.evidence import NO_ANSWER

from hannibal_contracts.doctrine import AnswerLanguage
from hannibal_doctrine.application.drafting import AnswerDrafter
from hannibal_doctrine.application.evidence import EvidenceValidation
from hannibal_doctrine.application.extracts import Extract, format_context
from hannibal_doctrine.application.ports import ChatModel, PassageIndex, SearchScope
from hannibal_doctrine.application.refusal import Refusal
from hannibal_doctrine.application.retrieve import RetrievePassages
from hannibal_doctrine.application.rewrite import QueryRewriter
from hannibal_doctrine.application.term_advice import AdviseOnTerms, TermAdvice

FIRST_TRY_EXTRACT_CHARS = 1800
SECOND_TRY_EXTRACT_CHARS = 2600


@dataclass(frozen=True, slots=True)
class AnsweringPolicy:
    extracts: int
    retry_extracts: int
    fallback_model: str
    quoted_style: bool
    detailed_headings: bool
    retry_with_reasoning: bool
    context_window: int
    classified_publications: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class DoctrineResult:
    answer: str
    refusal: Refusal | None
    cited: list[Extract]
    advice: TermAdvice
    query_en: str
    model: str
    index_version: str
    thresholds: dict[str, float]
    duration_ms: int
    second_try: bool = False


@dataclass(frozen=True, slots=True)
class Attempt:
    answer: str
    refusal: Refusal | None
    model: str
    cited: list[Extract] = field(default_factory=list)


class AskDoctrine:
    def __init__(
        self,
        *,
        rewriter: QueryRewriter,
        retrieve: RetrievePassages,
        drafter: AnswerDrafter,
        evidence: EvidenceValidation,
        advise: AdviseOnTerms,
        index: PassageIndex,
        chat: ChatModel,
        policy: AnsweringPolicy,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._rewriter = rewriter
        self._retrieve = retrieve
        self._drafter = drafter
        self._evidence = evidence
        self._advise = advise
        self._index = index
        self._chat = chat
        self._policy = policy
        self._clock = clock

    @property
    def thresholds(self) -> dict[str, float]:
        return {
            "min_similarity": self._evidence.min_similarity,
            "extracts": self._policy.extracts,
            "retry_extracts": self._policy.retry_extracts,
            "context_window": self._policy.context_window,
        }

    def scope(self, publications: Sequence[str], include_classified: bool) -> SearchScope:
        return SearchScope(
            only=tuple(publications),
            excluded=() if include_classified else self._policy.classified_publications,
        )

    async def __call__(
        self, question: str, language: AnswerLanguage, publications: Sequence[str], include_classified: bool
    ) -> DoctrineResult:
        started = self._clock()
        scope = self.scope(publications, include_classified)
        rewrite = await self._rewriter(question)
        retrieval = await self._retrieve(question, rewrite.query_en, scope, self._policy.extracts)
        extracts = [
            Extract(number=i + 1, passage=hit.passage, similarity=hit.similarity, table_row=hit.table_row)
            for i, hit in enumerate(retrieval.passages)
        ]
        refusal = self._evidence.coverage(retrieval.best_similarity, len(extracts))
        attempt, second_try = (
            (Attempt("", refusal, self._chat.default_model), False)
            if refusal
            else await self._answer(question, language, rewrite.query_en, extracts, scope)
        )
        advice = await self._advise(question, rewrite.query_en, scope)
        return DoctrineResult(
            answer=NO_ANSWER[language] if attempt.refusal else attempt.answer,
            refusal=attempt.refusal,
            cited=[] if attempt.refusal else attempt.cited,
            advice=advice,
            query_en=rewrite.query_en,
            model=attempt.model,
            index_version=await self._index.index_version(),
            thresholds=self.thresholds,
            duration_ms=round((self._clock() - started) * 1000),
            second_try=second_try,
        )

    async def _answer(
        self,
        question: str,
        language: AnswerLanguage,
        query_en: str,
        extracts: list[Extract],
        scope: SearchScope,
    ) -> tuple[Attempt, bool]:
        policy = self._policy
        context = format_context(
            extracts, FIRST_TRY_EXTRACT_CHARS, detailed_headings=policy.detailed_headings
        )
        if policy.quoted_style:
            draft = await self._drafter.quoted_answer(question, language, extracts, context)
            cited = [e for e in extracts if e.number in draft.cited]
            return Attempt(draft.text, draft.refusal, self._chat.default_model, cited), False
        first = await self._attempt(question, language, query_en, extracts, context, scope)
        if first.refusal is None or policy.retry_extracts <= 0:
            return first, False
        best = extracts[: policy.retry_extracts]
        short_context = format_context(
            best, SECOND_TRY_EXTRACT_CHARS, detailed_headings=policy.detailed_headings
        )
        second = await self._attempt(
            question,
            language,
            query_en,
            best,
            short_context,
            scope,
            reasoning=True if policy.retry_with_reasoning else None,
        )
        if second.refusal is None:
            return second, True
        if policy.fallback_model:
            fallback = await self._attempt(
                question, language, query_en, extracts, context, scope, model=policy.fallback_model
            )
            if fallback.refusal is None:
                return fallback, True
        return first, True

    async def _attempt(
        self,
        question: str,
        language: AnswerLanguage,
        query_en: str,
        extracts: list[Extract],
        context: str,
        scope: SearchScope,
        *,
        model: str | None = None,
        reasoning: bool | None = None,
    ) -> Attempt:
        used_model = model or self._chat.default_model
        draft = await self._drafter.cited_answer(
            question, language, extracts, context, model=model, reasoning=reasoning
        )
        if draft.refusal:
            return Attempt(draft.text, draft.refusal, used_model)
        cited = [e for e in extracts if e.number in draft.cited]
        refusal = await self._evidence.support(question, query_en, draft.text, cited, scope)
        return Attempt(draft.text, refusal, used_model, cited)
