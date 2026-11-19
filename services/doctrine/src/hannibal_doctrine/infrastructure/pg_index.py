"""Lecture du schéma `v2` (pgvector) avec le rôle `hannibal_doctrine`, en lecture seule.

Le schéma garde son nom pour ne pas réindexer ; seule la réindexation l'écrit (architecture 1.1.0 § 9).
"""

from collections.abc import Sequence
from typing import Any

import asyncpg
from hannibal_core.grounding.guard import corpus_pattern

from hannibal_doctrine.application.ports import Candidate, DependencyDown, GlossaryTerm, Passage, SearchScope

DEPENDENCY = "postgres"
HNSW_EF_SEARCH = 200
GLOSSARY_COLUMNS = "en, fr, sense, abbr, def_en, def_fr, source, page, statut"


def vector_literal(vector: Sequence[float]) -> str:
    return "[" + ",".join(f"{x:.6f}" for x in vector) + "]"


def scope_filter(scope: SearchScope, first_parameter: int, *, skip_toc: bool) -> tuple[str, list[Any]]:
    """Clause WHERE (sans le mot-clé) et ses paramètres, numérotés à partir de `first_parameter`."""
    clauses = ["kind <> 'toc'"] if skip_toc else ["TRUE"]
    parameters: list[Any] = []
    if scope.only:
        parameters.append(list(scope.only))
        clauses.append(f"pub = ANY(${first_parameter + len(parameters) - 1})")
    if scope.excluded:
        parameters.append(list(scope.excluded))
        clauses.append(f"NOT (pub = ANY(${first_parameter + len(parameters) - 1}))")
    return " AND ".join(clauses), parameters


async def _tune_connection(connection: asyncpg.Connection) -> None:
    await connection.execute(f"SET hnsw.ef_search = {HNSW_EF_SEARCH}")


class PgDoctrineStore:
    """`PassageIndex` et `GlossaryStore` sur la même réserve de connexions."""

    def __init__(self, dsn: str, *, min_connections: int = 1, max_connections: int = 4) -> None:
        self._dsn = dsn
        self._min = min_connections
        self._max = max_connections
        self._pool: asyncpg.Pool | None = None
        self._mentions: dict[tuple[str, bool, SearchScope], bool] = {}

    async def _connection_pool(self) -> asyncpg.Pool:
        if self._pool is None:
            try:
                self._pool = await asyncpg.create_pool(
                    self._dsn, min_size=self._min, max_size=self._max, init=_tune_connection
                )
            except (OSError, asyncpg.PostgresError) as error:
                raise DependencyDown(DEPENDENCY, str(error)) from error
        return self._pool

    async def _fetch(self, sql: str, *parameters: Any) -> list[asyncpg.Record]:
        pool = await self._connection_pool()
        try:
            return list(await pool.fetch(sql, *parameters))
        except (OSError, asyncpg.PostgresError) as error:
            raise DependencyDown(DEPENDENCY, str(error)) from error

    async def nearest_passages(
        self, vector: Sequence[float], scope: SearchScope, limit: int
    ) -> list[tuple[int, float]]:
        where, parameters = scope_filter(scope, 3, skip_toc=True)
        rows = await self._fetch(
            f"SELECT id, 1 - (embedding <=> $1::text::vector) AS score FROM v2.passages WHERE {where} "  # noqa: S608
            "ORDER BY embedding <=> $1::text::vector LIMIT $2",
            vector_literal(vector),
            limit,
            *parameters,
        )
        return [(int(r["id"]), float(r["score"])) for r in rows]

    async def nearest_generated_questions(
        self, vector: Sequence[float], scope: SearchScope, limit: int
    ) -> list[tuple[int, float]]:
        where, parameters = scope_filter(scope, 3, skip_toc=False)
        rows = await self._fetch(
            "SELECT passage_id, 1 - (embedding <=> $1::text::vector) AS score FROM v2.pquestions "  # noqa: S608
            f"WHERE {where} ORDER BY embedding <=> $1::text::vector LIMIT $2",
            vector_literal(vector),
            limit,
            *parameters,
        )
        return [(int(r["passage_id"]), float(r["score"])) for r in rows]

    async def nearest_table_rows(
        self, vector: Sequence[float], scope: SearchScope, limit: int
    ) -> list[tuple[int, str, float]]:
        where, parameters = scope_filter(scope, 3, skip_toc=False)
        rows = await self._fetch(
            "SELECT passage_id, row_text, 1 - (embedding <=> $1::text::vector) AS score FROM v2.prows "  # noqa: S608
            f"WHERE {where} ORDER BY embedding <=> $1::text::vector LIMIT $2",
            vector_literal(vector),
            limit,
            *parameters,
        )
        return [(int(r["passage_id"]), str(r["row_text"]), float(r["score"])) for r in rows]

    async def passages(self, ids: Sequence[int]) -> dict[int, Passage]:
        if not ids:
            return {}
        rows = await self._fetch(
            "SELECT id, pub, edition, chapter, section, article, title, page, pdf_page, text "
            "FROM v2.passages WHERE id = ANY($1)",
            list(ids),
        )
        return {
            int(r["id"]): Passage(
                id=int(r["id"]),
                publication=r["pub"],
                text=r["text"],
                edition=_text(r["edition"]),
                chapter=_text(r["chapter"]),
                section=_text(r["section"]),
                article=_text(r["article"]),
                title=_text(r["title"]),
                page=_text(r["page"]),
                pdf_page=r["pdf_page"],
            )
            for r in rows
        }

    async def mentions(self, term: str, scope: SearchScope, *, whole_word: bool) -> bool:
        key = (term.lower(), whole_word, scope)
        if key not in self._mentions:
            where, parameters = scope_filter(scope, 2, skip_toc=False)
            rows = await self._fetch(
                f"SELECT 1 FROM v2.passages WHERE text ~* $1 AND {where} LIMIT 1",  # noqa: S608
                corpus_pattern(term, word=whole_word),
                *parameters,
            )
            self._mentions[key] = bool(rows)
        return self._mentions[key]

    async def publications(self, scope: SearchScope) -> list[str]:
        where, parameters = scope_filter(scope, 1, skip_toc=False)
        rows = await self._fetch(
            f"SELECT DISTINCT pub FROM v2.passages WHERE {where} ORDER BY pub",  # noqa: S608
            *parameters,
        )
        return [str(r["pub"]) for r in rows]

    async def index_version(self) -> str:
        """Dernière ligne de `v2.index_versions` ; avant la première réindexation, le nombre de passages."""
        try:
            rows = await self._fetch("SELECT version FROM v2.index_versions ORDER BY created_at DESC LIMIT 1")
            if rows:
                return str(rows[0]["version"])
        except DependencyDown as error:
            if not isinstance(error.__cause__, asyncpg.UndefinedTableError):
                raise
        count = await self._fetch("SELECT count(*) AS n FROM v2.passages")
        return f"passages-{count[0]['n']}"

    async def lookup(self, query: str) -> list[GlossaryTerm]:
        rows = await self._fetch(
            f"SELECT {GLOSSARY_COLUMNS} FROM v2.glossary "  # noqa: S608
            "WHERE lower(en) = $1 OR lower(fr) = $1 OR lower(abbr) = $1 "
            "ORDER BY source, sense NULLS FIRST LIMIT 20",
            query,
        )
        if not rows:
            rows = await self._fetch(
                f"SELECT {GLOSSARY_COLUMNS} FROM v2.glossary "  # noqa: S608
                "WHERE lower(en) LIKE $1 OR lower(fr) LIKE $1 ORDER BY length(en), source LIMIT 12",
                query.replace("%", r"\%").replace("_", r"\_") + "%",
            )
        return [
            GlossaryTerm(
                en=r["en"],
                fr=r["fr"],
                sense=r["sense"],
                abbreviation=r["abbr"],
                definition_en=r["def_en"],
                definition_fr=r["def_fr"],
                source=r["source"],
                page=_text(r["page"]),
                status=r["statut"],
            )
            for r in rows
        ]

    async def acronym_candidates(self) -> list[Candidate]:
        rows = await self._fetch(
            "SELECT DISTINCT abbr, en, fr FROM v2.glossary WHERE abbr IS NOT NULL AND abbr <> ''"
        )
        return [
            (r["abbr"].strip(), r["en"], r["fr"] or "") for r in rows if 2 <= len(r["abbr"].strip()) <= 12
        ]

    async def word_candidates(self) -> list[Candidate]:
        rows = await self._fetch(
            "SELECT DISTINCT en, fr FROM v2.glossary WHERE en !~ ' ' AND length(en) BETWEEN 4 AND 24"
        )
        return [(r["en"].strip(), r["en"], r["fr"] or "") for r in rows]

    async def is_reachable(self) -> bool:
        try:
            await self._fetch("SELECT 1")
        except DependencyDown:
            return False
        return True

    async def aclose(self) -> None:
        if self._pool is not None:
            await self._pool.close()


def _text(value: object) -> str | None:
    return None if value is None else str(value)
