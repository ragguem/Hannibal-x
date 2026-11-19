from collections.abc import Sequence
from typing import Protocol


class PairScorer(Protocol):
    """Note la pertinence de chaque couple (question, passage). Appelé dans un thread, une fois à la fois."""

    @property
    def model_name(self) -> str: ...

    def score(self, pairs: Sequence[tuple[str, str]]) -> list[float]: ...
