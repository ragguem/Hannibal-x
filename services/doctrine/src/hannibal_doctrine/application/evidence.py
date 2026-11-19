"""Validation des preuves (architecture 1.1.0 § 7) : couverture, ancrage, vérification, dans cet ordre."""

import asyncio
import json
from dataclasses import dataclass

from hannibal_core.grounding.guard import grounded

from hannibal_contracts.doctrine import RefusalReason
from hannibal_doctrine.application.corpus_terms import CorpusTerms
from hannibal_doctrine.application.extracts import Extract
from hannibal_doctrine.application.ports import ChatModel, DependencyDown, PassageIndex, SearchScope
from hannibal_doctrine.application.prompts import VERIFIER_SYSTEM
from hannibal_doctrine.application.refusal import NO_CLOSE_PASSAGE, Refusal

VERIFIED_EXTRACT_CHARS = 1800


@dataclass(frozen=True, slots=True)
class Verdict:
    ok: bool
    why: str = ""
    checked: bool = True


class AnswerVerifier:
    """Second passage, indépendant. Contrôle en panne : la réponse passe, signalée comme non vérifiée."""

    def __init__(self, chat: ChatModel, *, reasoning: bool | None) -> None:
        self._chat = chat
        self._reasoning = reasoning

    async def __call__(self, question: str, answer: str, cited: list[Extract]) -> Verdict:
        extracts = "\n\n".join(
            f"[{e.number}] {e.passage.text[:VERIFIED_EXTRACT_CHARS]}"
            + (f"\nTable row: {e.table_row}" if e.table_row else "")
            for e in cited
        )
        try:
            raw = await self._chat.chat(
                VERIFIER_SYSTEM,
                f"QUESTION: {question}\n\nANSWER: {answer}\n\nEXTRACTS:\n{extracts}",
                output="json",
                reasoning=self._reasoning,
            )
            data = json.loads(raw)
            answers, supported = bool(data.get("answers_question")), bool(data.get("supported"))
        except (DependencyDown, ValueError, AttributeError):
            return Verdict(ok=True, why="contrôle indisponible", checked=False)
        if not answers:
            return Verdict(ok=False, why="la réponse ne traite pas la question")
        if not supported:
            return Verdict(ok=False, why="la réponse n'est pas appuyée par les extraits cités")
        return Verdict(ok=True)


class EvidenceValidation:
    def __init__(
        self,
        index: PassageIndex,
        verifier: AnswerVerifier,
        *,
        min_similarity: float,
        grounding_check: bool,
        whole_word_acronyms: bool,
    ) -> None:
        self._index = index
        self._verifier = verifier
        self.min_similarity = min_similarity
        self._grounding_check = grounding_check
        self._whole_word_acronyms = whole_word_acronyms

    def coverage(self, best_similarity: float, passages_found: int) -> Refusal | None:
        if passages_found == 0 or best_similarity < self.min_similarity:
            return Refusal(RefusalReason.NO_EVIDENCE, NO_CLOSE_PASSAGE)
        return None

    async def support(
        self, question: str, query_en: str, answer: str, cited: list[Extract], scope: SearchScope
    ) -> Refusal | None:
        if self._grounding_check:
            terms = CorpusTerms(self._index, scope, asyncio.get_running_loop())
            ok, why = await asyncio.to_thread(
                grounded,
                question,
                answer,
                [{"text": e.passage.text, "title": e.passage.title} for e in cited],
                query_en,
                in_corpus=terms.contains,
                in_corpus_word=terms.contains_word,
                word=self._whole_word_acronyms,
            )
            if not ok:
                return Refusal(RefusalReason.UNGROUNDED_CLAIM, f"contrôle : {why}")
        verdict = await self._verifier(question, answer, cited)
        if not verdict.ok:
            return Refusal(RefusalReason.UNSUPPORTED_ANSWER, f"vérification : {verdict.why}")
        return None
