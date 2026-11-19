"""Reclassement : chaque passage garde son meilleur score sur les requêtes (question et reformulation)."""

import asyncio
from collections.abc import Sequence

from hannibal_rerank.application.ports import PairScorer


class RankPassages:
    def __init__(
        self, scorer: PairScorer, *, max_queries: int, max_passages: int, max_passage_chars: int
    ) -> None:
        self._scorer = scorer
        self._max_queries = max_queries
        self._max_passages = max_passages
        self._max_passage_chars = max_passage_chars
        self._one_at_a_time = asyncio.Lock()

    @property
    def model_name(self) -> str:
        return self._scorer.model_name

    async def __call__(self, queries: Sequence[str], passages: Sequence[str]) -> list[float]:
        kept_queries = [query for query in queries if query.strip()][: self._max_queries]
        kept_passages = [passage[: self._max_passage_chars] for passage in passages[: self._max_passages]]
        if not kept_queries or not kept_passages:
            return [0.0] * len(kept_passages)
        best = [float("-inf")] * len(kept_passages)
        async with self._one_at_a_time:
            for query in kept_queries:
                pairs = [(query, passage) for passage in kept_passages]
                scores = await asyncio.to_thread(self._scorer.score, pairs)
                best = [max(previous, score) for previous, score in zip(best, scores, strict=True)]
        return best
