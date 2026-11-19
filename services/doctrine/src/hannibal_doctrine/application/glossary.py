from hannibal_doctrine.application.ports import GlossaryStore, GlossaryTerm


class LookupGlossary:
    """Terme anglais, français ou abréviation → définitions officielles (égalité, puis début du mot)."""

    def __init__(self, store: GlossaryStore) -> None:
        self._store = store

    async def __call__(self, query: str) -> list[GlossaryTerm]:
        query = query.strip().lower()
        return await self._store.lookup(query) if query else []
