"""Extraits numérotés : ce que le modèle voit, ce que l'opérateur relit."""

import re
from dataclasses import dataclass

from hannibal_doctrine.application.ports import Passage

CITATION = re.compile(r"\[(\d+)\]")


@dataclass(frozen=True, slots=True)
class Extract:
    number: int
    passage: Passage
    similarity: float
    table_row: str | None = None


def format_extract(extract: Extract, max_chars: int, *, detailed_headings: bool) -> str:
    """Publication, (chapitre, section), article, page, titre, texte ; et la ligne de tableau proche."""
    p = extract.passage
    head = f"[{extract.number}] {p.publication}"
    if detailed_headings and p.chapter:
        head += f", chap. {p.chapter}"
    if detailed_headings and p.section:
        head += f", {p.section}"
    head += f", art. {p.article or '-'}, p. {p.page or '-'} — {p.title or ''}"
    row = (
        f"\nLigne du tableau la plus proche de la question / closest table row: {extract.table_row}"
        if extract.table_row
        else ""
    )
    return f"{head}\n{p.text[:max_chars]}{row}"


def format_context(extracts: list[Extract], max_chars: int, *, detailed_headings: bool) -> str:
    return "\n\n".join(format_extract(e, max_chars, detailed_headings=detailed_headings) for e in extracts)


def cited_numbers(answer: str, count: int) -> tuple[list[int], list[int]]:
    """-> (numéros valides cités, numéros hors des extraits)."""
    numbers = [int(n) for n in CITATION.findall(answer)]
    valid = sorted({n for n in numbers if 1 <= n <= count})
    return valid, [n for n in numbers if not 1 <= n <= count]
