"""Recherche d'un terme dans les publications, pour les contrôles synchrones de `hannibal_core.grounding`.

Les contrôles tournent dans un thread ; chaque recherche est renvoyée à la boucle asynchrone et mise en cache
pour la durée d'une question.
"""

import asyncio
from collections.abc import Callable

from hannibal_doctrine.application.ports import PassageIndex, SearchScope

LOOKUP_TIMEOUT_S = 30.0


class CorpusTerms:
    def __init__(self, index: PassageIndex, scope: SearchScope, loop: asyncio.AbstractEventLoop) -> None:
        self._index = index
        self._scope = scope
        self._loop = loop
        self._known: dict[tuple[str, bool], bool] = {}

    def _lookup(self, term: str, whole_word: bool) -> bool:
        key = (term.lower(), whole_word)
        if key not in self._known:
            future = asyncio.run_coroutine_threadsafe(
                self._index.mentions(term, self._scope, whole_word=whole_word), self._loop
            )
            self._known[key] = future.result(timeout=LOOKUP_TIMEOUT_S)
        return self._known[key]

    def contains(self, term: str) -> bool:
        return self._lookup(term, False)

    def contains_word(self, term: str) -> bool:
        """Mot entier : « RAZ » n'est pas trouvé dans « razor »."""
        return self._lookup(term, True)

    @property
    def lookups(self) -> tuple[Callable[[str], bool], Callable[[str], bool]]:
        return self.contains, self.contains_word
