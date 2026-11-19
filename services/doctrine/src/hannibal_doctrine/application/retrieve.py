"""Recherche des passages (legacy `search2`).

Vecteurs sur la question d'origine et sur sa reformulation anglaise, meilleure similarité des deux (essais du
12/11 : top 5 à 92 %, top 10 à 95 % ; la fusion avec les mots-clés dégradait). Options : questions générées
par passage, lignes de tableaux. Puis reclassement des 30 premiers par le service `rerank` s'il répond.
"""

from collections.abc import Sequence
from dataclasses import dataclass

from hannibal_doctrine.application.ports import Embedder, Passage, PassageIndex, Reranker, SearchScope

VECTOR_CANDIDATES = 40
POOL_SIZE = 30
GENERATED_QUESTION_CANDIDATES = 60
GENERATED_QUESTION_POOL = 25
MERGED_POOL_SIZE = 45
TABLE_ROW_CANDIDATES = 40
TABLE_ROWS_KEPT = 12


@dataclass(frozen=True, slots=True)
class RetrievedPassage:
    passage: Passage
    similarity: float
    relevance: float
    table_row: str | None = None


@dataclass(frozen=True, slots=True)
class Retrieval:
    passages: list[RetrievedPassage]
    reranked: bool = False
    generated_questions: int = 0
    table_rows: int = 0

    @property
    def best_similarity(self) -> float:
        return max((p.similarity for p in self.passages), default=0.0)


def interleave(first: Sequence[int], second: Sequence[int], limit: int) -> list[int]:
    merged: list[int] = []
    for index in range(max(len(first), len(second))):
        for candidates in (first, second):
            if index < len(candidates) and candidates[index] not in merged:
                merged.append(candidates[index])
    return merged[:limit]


class RetrievePassages:
    def __init__(
        self,
        index: PassageIndex,
        embedder: Embedder,
        reranker: Reranker,
        *,
        use_generated_questions: bool,
        use_table_rows: bool,
    ) -> None:
        self._index = index
        self._embedder = embedder
        self._reranker = reranker
        self._use_generated_questions = use_generated_questions
        self._use_table_rows = use_table_rows

    async def __call__(self, question: str, query_en: str, scope: SearchScope, limit: int) -> Retrieval:
        queries = [question] + ([query_en] if query_en else [])
        vectors = [await self._embedder.embed(text) for text in queries]

        similarity: dict[int, float] = {}
        for vector in vectors:
            for passage_id, score in await self._index.nearest_passages(vector, scope, VECTOR_CANDIDATES):
                similarity[passage_id] = max(similarity.get(passage_id, 0.0), score)
        relevance = dict(similarity)
        pool = sorted(similarity, key=lambda pid: -similarity[pid])[:POOL_SIZE]

        generated = 0
        if self._use_generated_questions:
            by_question: dict[int, float] = {}
            for vector in vectors:
                for pid, score in await self._index.nearest_generated_questions(
                    vector, scope, GENERATED_QUESTION_CANDIDATES
                ):
                    by_question[pid] = max(by_question.get(pid, 0.0), score)
            ranked = sorted(by_question, key=lambda pid: -by_question[pid])[:GENERATED_QUESTION_POOL]
            generated = len(ranked)
            pool = interleave(pool, ranked, MERGED_POOL_SIZE)
            for pid in pool:
                relevance.setdefault(pid, by_question.get(pid, 0.0))
                similarity.setdefault(pid, 0.0)

        closest_row: dict[int, tuple[str, float]] = {}
        if self._use_table_rows:
            for vector in vectors:
                for pid, row, score in await self._index.nearest_table_rows(
                    vector, scope, TABLE_ROW_CANDIDATES
                ):
                    if pid not in closest_row or score > closest_row[pid][1]:
                        closest_row[pid] = (row, score)
            kept = sorted(closest_row, key=lambda pid: -closest_row[pid][1])[:TABLE_ROWS_KEPT]
            closest_row = {pid: closest_row[pid] for pid in kept}
            for pid in kept:
                if pid not in pool:
                    pool.append(pid)
                relevance.setdefault(pid, closest_row[pid][1])
                similarity.setdefault(pid, 0.0)

        passages = await self._index.passages(pool)
        pool = [pid for pid in pool if pid in passages]
        order, reranked = await self._rerank(queries, pool, passages, closest_row, relevance)
        top = order[:limit]
        return Retrieval(
            passages=[
                RetrievedPassage(
                    passage=passages[pid],
                    similarity=round(similarity.get(pid, 0.0), 4),
                    relevance=round(relevance[pid], 5),
                    table_row=closest_row[pid][0].split("] ", 1)[-1] if pid in closest_row else None,
                )
                for pid in top
            ],
            reranked=reranked,
            generated_questions=generated,
            table_rows=len(closest_row),
        )

    async def _rerank(
        self,
        queries: list[str],
        pool: list[int],
        passages: dict[int, Passage],
        closest_row: dict[int, tuple[str, float]],
        relevance: dict[int, float],
    ) -> tuple[list[int], bool]:
        if not pool:
            return [], False
        with_rows = [pid for pid in pool if pid in closest_row]
        texts = [f"{passages[pid].title or ''}. {passages[pid].text}" for pid in pool]
        scores = await self._reranker.rerank(queries, texts + [closest_row[pid][0] for pid in with_rows])
        if scores is None or len(scores) != len(texts) + len(with_rows):
            return pool, False
        by_passage = dict(zip(pool, scores[: len(pool)], strict=True))
        for pid, row_score in zip(with_rows, scores[len(pool) :], strict=True):
            by_passage[pid] = max(by_passage[pid], row_score)  # un tableau vaut sa meilleure ligne
        relevance.update(by_passage)
        return sorted(pool, key=lambda pid: -by_passage[pid]), True
