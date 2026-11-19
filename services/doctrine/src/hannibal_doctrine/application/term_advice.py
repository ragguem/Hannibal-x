"""« Vouliez-vous dire… ? » : un sigle mal dicté fait refuser ; on propose, l'opérateur choisit."""

import asyncio
from dataclasses import dataclass, field
from typing import Any

from hannibal_core.grounding.evidence import suggest, unknown_terms

from hannibal_doctrine.application.corpus_terms import CorpusTerms
from hannibal_doctrine.application.ports import (
    Candidate,
    DependencyDown,
    GlossaryStore,
    PassageIndex,
    SearchScope,
)


@dataclass(frozen=True, slots=True)
class TermAdvice:
    unknown: list[str] = field(default_factory=list)
    suggestions: list[dict[str, Any]] = field(default_factory=list)


class AdviseOnTerms:
    def __init__(self, index: PassageIndex, glossary: GlossaryStore) -> None:
        self._index = index
        self._glossary = glossary
        self._candidates: tuple[list[Candidate], list[Candidate]] | None = None

    async def _glossary_candidates(self) -> tuple[list[Candidate], list[Candidate]]:
        if self._candidates is None:
            self._candidates = (
                await self._glossary.acronym_candidates(),
                await self._glossary.word_candidates(),
            )
        return self._candidates

    async def __call__(self, question: str, query_en: str, scope: SearchScope) -> TermAdvice:
        """Ajouté à toute réponse, refus ou non : une réponse malgré un sigle inconnu doit être signalée."""
        try:
            acronyms, words = await self._glossary_candidates()
            terms = CorpusTerms(self._index, scope, asyncio.get_running_loop())
            found = await asyncio.to_thread(
                unknown_terms,
                question,
                query_en,
                in_corpus=terms.contains,
                in_corpus_word=terms.contains_word,
                suggest_for=lambda term: suggest(term, acronyms, words, terms.contains_word),
            )
        except (DependencyDown, TimeoutError):
            return TermAdvice()
        return TermAdvice(unknown=found.get("termes_inconnus", []), suggestions=found.get("suggestions", []))
