"""Explication d'un ordre (RAG v1, legacy/hx/scripts/rag.py `explain`).

Le modèle reformule l'interprétation déterministe à partir des passages proches ; sa réponse est contrôlée
(bord, cap vrai, valeurs) et corrigée une fois. Si elle échoue encore, on rend l'interprétation déterministe.
"""

import json
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field

from hannibal_core.grounding.explanation import explanation_errors, parameters_en, parameters_fr

from hannibal_contracts.doctrine import ExplanationSource
from hannibal_doctrine.application.extracts import Extract
from hannibal_doctrine.application.ports import ChatModel, DependencyDown, Embedder, PassageIndex, SearchScope
from hannibal_doctrine.application.prompts import EXPLAIN_SCHEMA, EXPLAIN_SYSTEM

ATTEMPTS = 2
CONTEXT_EXTRACT_CHARS = 1400


@dataclass(frozen=True, slots=True)
class OrderExplanation:
    explanation_en: str
    explanation_fr: str
    source: ExplanationSource
    model: str
    duration_ms: int
    cited: list[Extract] = field(default_factory=list)
    rejected_checks: list[str] = field(default_factory=list)


def deterministic_explanation(
    meaning_en: str, meaning_fr: str, parameters: Mapping[str, int | str]
) -> tuple[str, str]:
    if not parameters:
        return meaning_en, meaning_fr
    return (
        f"{meaning_en} Parameters: {parameters_en(parameters)}.",
        f"{meaning_fr} Paramètres : {parameters_fr(parameters)}.",
    )


class ExplainOrder:
    def __init__(
        self,
        index: PassageIndex,
        embedder: Embedder,
        chat: ChatModel,
        *,
        classified_publications: tuple[str, ...],
        extracts: int = 3,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._index = index
        self._embedder = embedder
        self._chat = chat
        self._scope = SearchScope(excluded=classified_publications)
        self._extracts = extracts
        self._clock = clock

    async def _context(self, meaning_en: str) -> list[Extract]:
        try:
            nearest = await self._index.nearest_passages(
                await self._embedder.embed(meaning_en), self._scope, self._extracts
            )
            passages = await self._index.passages([pid for pid, _ in nearest])
        except DependencyDown:
            return []
        found = [(pid, score) for pid, score in nearest if pid in passages]
        return [
            Extract(number=i + 1, passage=passages[pid], similarity=score)
            for i, (pid, score) in enumerate(found)
        ]

    async def __call__(
        self, message: str, meaning_en: str, meaning_fr: str, parameters: Mapping[str, int | str]
    ) -> OrderExplanation:
        started = self._clock()
        extracts = await self._context(meaning_en)
        prompt = (
            f"RADIO MESSAGE:\n{message}\n\n"
            f"DECODED MEANING: {meaning_en}\nDECODED MEANING (FRENCH): {meaning_fr}\n"
            f"DECODED PARAMETERS: {json.dumps(dict(parameters))}\n"
            f"MEANING OF THE PARAMETERS: {parameters_en(parameters)}\n"
            f"DECODED PARAMETERS (FRENCH): {parameters_fr(parameters)}\n\n"
            + "\n\n".join(
                f"PASSAGE [{e.number}] — {e.passage.publication}, art. {e.passage.article or '-'}, "
                f"p. {e.passage.page or '-'}\n{e.passage.text[:CONTEXT_EXTRACT_CHARS]}"
                for e in extracts
            )
        )
        errors = ["pas de réponse"]
        answer: dict[str, object] = {}
        feedback = ""
        for _ in range(ATTEMPTS):
            try:
                raw = await self._chat.chat(EXPLAIN_SYSTEM, prompt + feedback, output=EXPLAIN_SCHEMA)
                parsed = json.loads(raw)
            except DependencyDown:
                errors = ["modèle indisponible"]
                break
            except ValueError:
                errors = ["réponse du modèle illisible"]
                continue
            answer = parsed if isinstance(parsed, dict) else {}
            errors = explanation_errors(
                str(answer.get("explanation_en") or ""), str(answer.get("explanation_fr") or ""), parameters
            )
            if not errors:
                break
            feedback = (
                f"\n\nYOUR PREVIOUS ANSWER: {json.dumps(answer, ensure_ascii=False)}\n"
                f"It failed these checks: {'; '.join(errors)}. Correct it and answer again in JSON."
            )
        duration_ms = round((self._clock() - started) * 1000)
        if errors:
            en, fr = deterministic_explanation(meaning_en, meaning_fr, parameters)
            return OrderExplanation(
                en, fr, ExplanationSource.DETERMINISTIC, self._chat.default_model, duration_ms, [], errors
            )
        references = answer.get("references_used")
        used = {int(n) for n in references if isinstance(n, int)} if isinstance(references, list) else set()
        return OrderExplanation(
            str(answer["explanation_en"]),
            str(answer["explanation_fr"]),
            ExplanationSource.CHECKED_MODEL,
            self._chat.default_model,
            duration_ms,
            [e for e in extracts if e.number in used],
        )
