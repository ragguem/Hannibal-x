"""Adaptateurs d'exemple (`HX_DOCTRINE_ADAPTERS=sample`) : poste sans GPU ni base, tests, démonstration hors ligne.

Le corpus et le glossaire sont INVENTÉS pour ce dépôt : aucun texte n'est tiré d'une publication. Le modèle
scripté répond par la première phrase de l'extrait le plus proche, ce qui suffit à exercer tout le pipeline.
"""

import hashlib
import json
import re
from collections.abc import Sequence
from typing import Any

from hannibal_core.grounding.guard import STOPWORDS

from hannibal_doctrine.application.ports import Candidate, GlossaryTerm, Passage, SearchScope
from hannibal_doctrine.application.prompts import (
    CITED_ANSWER_SYSTEM,
    EXPLAIN_SYSTEM,
    NO_SOURCE_MARKER,
    QUOTED_ANSWER_SYSTEM,
    REWRITE_SYSTEM,
    VERIFIER_SYSTEM,
)

DIMENSIONS = 1024
WORD = re.compile(r"[a-z0-9]{2,}")
SAMPLE_PUBLICATION = "DEMO-MANUEL"

SAMPLE_PASSAGES = (
    Passage(1, SAMPLE_PUBLICATION, "When the guide orders a CORPEN signal, every ship of the formation wheels in "
            "succession to the new true course and keeps its station. The order is executed on the word EXECUTE.",
            edition="A", chapter="1", article="101", title="Course changes in formation", page="1-3"),
    Passage(2, SAMPLE_PUBLICATION, "The formation speed is ordered by the guide. A ship that cannot keep the ordered "
            "speed reports it at once. The standard tactical speed is 12 knots unless another speed is ordered.",
            edition="A", chapter="1", article="102", title="Formation speed", page="1-4"),
    Passage(3, SAMPLE_PUBLICATION, "During a replenishment at sea approach, the receiving ship keeps a separation of "
            "40 metres from the delivering ship and closes at no more than 3 knots above the replenishment speed.",
            edition="A", chapter="2", article="205", title="Replenishment at sea approach", page="2-7"),
    Passage(4, SAMPLE_PUBLICATION, "The delivering ship hoists the ROMEO flag close up when it is ready to receive "
            "the approach of the receiving ship.",
            edition="A", chapter="2", article="206", title="Replenishment signals", page="2-8"),
)  # fmt: skip
RESTRICTED_TEXT = (
    "The silent manoeuvre procedure is described in the restricted annex and is not repeated here."
)

SAMPLE_GLOSSARY = (
    GlossaryTerm("replenishment at sea", "DEMO-GLOSSAIRE", fr="ravitaillement à la mer", abbreviation="RAS",
                 definition_fr="Transfert de combustible, de vivres ou de munitions entre navires en route."),
    GlossaryTerm("officer in tactical command", "DEMO-GLOSSAIRE", fr="commandant tactique", abbreviation="OTC",
                 definition_fr="Officier qui exerce le commandement tactique de la formation."),
    GlossaryTerm("course", "DEMO-GLOSSAIRE", fr="cap", definition_fr="Direction suivie par le navire."),
    GlossaryTerm("station", "DEMO-GLOSSAIRE", fr="poste", definition_fr="Position assignée dans la formation."),
)  # fmt: skip

FRENCH_TO_ENGLISH = {
    "vitesse": "speed",
    "cap": "course",
    "ravitaillement": "replenishment",
    "navire": "ship",
    "navires": "ships",
    "formation": "formation",
    "pavillon": "flag",
    "distance": "separation",
    "écart": "separation",
}


def content_words(text: str) -> list[str]:
    return [w for w in WORD.findall(text.lower()) if w not in STOPWORDS]


class HashedWordsEmbedder:
    """Sac de mots sans modèle : chaque mot allume une dimension. La similarité se lit comme une part de mots."""

    model_name = "hashed-words"

    async def embed(self, text: str) -> list[float]:
        vector = [0.0] * DIMENSIONS
        for word in content_words(text):
            vector[int(hashlib.blake2s(word.encode(), digest_size=4).hexdigest(), 16) % DIMENSIONS] = 1.0
        return vector


def overlap(query: Sequence[float], passage: Sequence[float]) -> float:
    asked = sum(query)
    return sum(q * p for q, p in zip(query, passage, strict=True)) / asked if asked else 0.0


class SampleCorpus:
    def __init__(self, restricted_publication: str | None = None) -> None:
        self._passages = list(SAMPLE_PASSAGES)
        if restricted_publication:
            self._passages.append(
                Passage(9, restricted_publication, RESTRICTED_TEXT, article="C-1", title="Silent manoeuvres")
            )
        self._embedder = HashedWordsEmbedder()
        self._vectors: dict[int, list[float]] = {}

    async def _vector(self, passage: Passage) -> list[float]:
        if passage.id not in self._vectors:
            self._vectors[passage.id] = await self._embedder.embed(f"{passage.title or ''} {passage.text}")
        return self._vectors[passage.id]

    async def nearest_passages(
        self, vector: Sequence[float], scope: SearchScope, limit: int
    ) -> list[tuple[int, float]]:
        scored = [
            (p.id, overlap(vector, await self._vector(p)))
            for p in self._passages
            if scope.allows(p.publication)
        ]
        return sorted(scored, key=lambda item: -item[1])[:limit]

    async def nearest_generated_questions(
        self, vector: Sequence[float], scope: SearchScope, limit: int
    ) -> list[tuple[int, float]]:
        return []

    async def nearest_table_rows(
        self, vector: Sequence[float], scope: SearchScope, limit: int
    ) -> list[tuple[int, str, float]]:
        return []

    async def passages(self, ids: Sequence[int]) -> dict[int, Passage]:
        return {p.id: p for p in self._passages if p.id in ids}

    async def mentions(self, term: str, scope: SearchScope, *, whole_word: bool) -> bool:
        pattern = re.compile(r"\b" + re.escape(term) + r"\b" if whole_word else re.escape(term), re.I)
        return any(scope.allows(p.publication) and pattern.search(p.text) for p in self._passages)

    async def publications(self, scope: SearchScope) -> list[str]:
        return sorted({p.publication for p in self._passages if scope.allows(p.publication)})

    async def index_version(self) -> str:
        return f"sample-{len(self._passages)}"

    async def lookup(self, query: str) -> list[GlossaryTerm]:
        exact = [
            t
            for t in SAMPLE_GLOSSARY
            if query in (t.en, (t.fr or "").lower(), (t.abbreviation or "").lower())
        ]
        return exact or [
            t for t in SAMPLE_GLOSSARY if t.en.startswith(query) or (t.fr or "").startswith(query)
        ]

    async def acronym_candidates(self) -> list[Candidate]:
        return [(t.abbreviation, t.en, t.fr or "") for t in SAMPLE_GLOSSARY if t.abbreviation]

    async def word_candidates(self) -> list[Candidate]:
        return [(t.en, t.en, t.fr or "") for t in SAMPLE_GLOSSARY if " " not in t.en]


def numbered_extracts(prompt: str) -> dict[int, str]:
    extracts = {}
    for block in prompt.split("\n\n"):
        head, _, text = block.partition("\n")
        if match := re.match(r"\[(\d+)\] ", head):
            extracts[int(match.group(1))] = text
    return extracts


class ScriptedChatModel:
    """Répond sans modèle, selon la consigne reçue. Remplace Ollama dans les tests et le mode `sample`."""

    default_model = "scripted"

    async def chat(
        self,
        system: str,
        user: str,
        *,
        model: str | None = None,
        output: str | dict[str, Any] | None = None,
        reasoning: bool | None = None,
    ) -> str:
        if system == REWRITE_SYSTEM:
            words = [FRENCH_TO_ENGLISH.get(w, w) for w in WORD.findall(user.lower())]
            return json.dumps({"query": " ".join(words), "keywords": []})
        if system == VERIFIER_SYSTEM:
            return json.dumps({"answers_question": True, "supported": True, "why": ""})
        if system == EXPLAIN_SYSTEM:
            meaning = dict(re.findall(r"^DECODED MEANING( \(FRENCH\))?: (.*)$", user, re.M))
            return json.dumps(
                {
                    "explanation_en": meaning.get("", ""),
                    "explanation_fr": meaning.get(" (FRENCH)", ""),
                    "references_used": [1],
                }
            )
        question = user.rsplit("Question : ", 1)[-1]
        number, sentence = self._closest_sentence(question, numbered_extracts(user))
        if system in QUOTED_ANSWER_SYSTEM.values():
            if not number:
                return json.dumps({"quotes": [], "answer": NO_SOURCE_MARKER})
            return json.dumps(
                {"quotes": [{"n": number, "text": sentence}], "answer": f"{sentence} [{number}]"}
            )
        if system.startswith(tuple(CITED_ANSWER_SYSTEM.values())):
            return f"{sentence} [{number}]" if number else NO_SOURCE_MARKER
        return ""

    @staticmethod
    def _closest_sentence(question: str, extracts: dict[int, str]) -> tuple[int, str]:
        asked = {FRENCH_TO_ENGLISH.get(w, w) for w in content_words(question)}
        best = (0, 0, "")
        for number, text in extracts.items():
            for sentence in re.split(r"(?<=\.)\s+", text):
                shared = len(asked & set(content_words(sentence)))
                if shared > best[0]:
                    best = (shared, number, sentence.strip())
        return best[1], best[2]
