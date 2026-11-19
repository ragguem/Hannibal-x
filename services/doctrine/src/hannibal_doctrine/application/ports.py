"""Ports du pipeline documentaire. Les adaptateurs réels lisent `v2` en lecture seule et parlent à Ollama."""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True, slots=True)
class Passage:
    id: int
    publication: str
    text: str
    edition: str | None = None
    chapter: str | None = None
    section: str | None = None
    article: str | None = None
    title: str | None = None
    page: str | None = None
    pdf_page: int | None = None


@dataclass(frozen=True, slots=True)
class SearchScope:
    """Publications où chercher : `only` restreint (vide = toutes), `excluded` retire."""

    only: tuple[str, ...] = ()
    excluded: tuple[str, ...] = ()

    def allows(self, publication: str) -> bool:
        return publication not in self.excluded and (not self.only or publication in self.only)


@dataclass(frozen=True, slots=True)
class GlossaryTerm:
    en: str
    source: str
    fr: str | None = None
    sense: int | None = None
    abbreviation: str | None = None
    definition_en: str | None = None
    definition_fr: str | None = None
    page: str | None = None
    status: str | None = None


Candidate = tuple[str, str, str]  # (terme proposé, anglais, français)


class DependencyDown(Exception):
    """Une dépendance du pipeline (Ollama, base vectorielle) ne répond pas : la question échoue en `503`."""

    def __init__(self, dependency: str, detail: str) -> None:
        super().__init__(detail)
        self.dependency = dependency


class PassageIndex(Protocol):
    """Passages (`v2.passages`), lignes de tableaux (`v2.prows`), questions générées (`v2.pquestions`)."""

    async def nearest_passages(
        self, vector: Sequence[float], scope: SearchScope, limit: int
    ) -> list[tuple[int, float]]: ...

    async def nearest_generated_questions(
        self, vector: Sequence[float], scope: SearchScope, limit: int
    ) -> list[tuple[int, float]]: ...

    async def nearest_table_rows(
        self, vector: Sequence[float], scope: SearchScope, limit: int
    ) -> list[tuple[int, str, float]]: ...

    async def passages(self, ids: Sequence[int]) -> dict[int, Passage]: ...

    async def mentions(self, term: str, scope: SearchScope, *, whole_word: bool) -> bool:
        """Le terme figure-t-il dans une publication du périmètre ? Variantes SM-2, SM 2, SM2 tolérées."""
        ...

    async def publications(self, scope: SearchScope) -> list[str]: ...

    async def index_version(self) -> str: ...


class GlossaryStore(Protocol):
    async def lookup(self, query: str) -> list[GlossaryTerm]: ...

    async def acronym_candidates(self) -> list[Candidate]: ...

    async def word_candidates(self) -> list[Candidate]: ...


class Embedder(Protocol):
    @property
    def model_name(self) -> str: ...

    async def embed(self, text: str) -> list[float]: ...


class ChatModel(Protocol):
    """Modèle de langage local, température nulle. `output` : `None` (texte), `"json"` ou un schéma JSON."""

    @property
    def default_model(self) -> str: ...

    async def chat(
        self,
        system: str,
        user: str,
        *,
        model: str | None = None,
        output: str | dict[str, Any] | None = None,
        reasoning: bool | None = None,
    ) -> str: ...


class Reranker(Protocol):
    async def rerank(self, queries: Sequence[str], passages: Sequence[str]) -> list[float] | None:
        """Scores dans l'ordre des passages ; `None` si le service manque (on garde l'ordre des vecteurs)."""
        ...
