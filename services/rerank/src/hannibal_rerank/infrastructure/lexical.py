"""Classeur sans modèle : part des mots de la question présents dans le passage. Poste sans GPU et tests."""

import re
from collections.abc import Sequence

WORD = re.compile(r"[a-z0-9]{3,}")


def words(text: str) -> set[str]:
    return set(WORD.findall(text.lower()))


class LexicalOverlapScorer:
    model_name = "lexical-overlap"

    def score(self, pairs: Sequence[tuple[str, str]]) -> list[float]:
        scores = []
        for query, passage in pairs:
            asked = words(query)
            scores.append(len(asked & words(passage)) / len(asked) if asked else 0.0)
        return scores
