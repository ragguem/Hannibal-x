"""Contrôle d'ancrage d'une réponse de doctrine, sans modèle.

Repris de legacy/v2/scripts/hx2_service_c.py (`key_terms`, `grounded`). La recherche dans les publications
chargées est fournie par l'appelant (`in_corpus`, `in_corpus_word`) : elle filtre déjà les publications classifiées.
"""

import re
from collections.abc import Callable, Iterable
from typing import Any

CorpusLookup = Callable[[str], bool]

STOPWORDS = set(
    [
        "le",
        "la",
        "les",
        "un",
        "une",
        "des",
        "du",
        "de",
        "au",
        "aux",
        "en",
        "et",
        "ou",
        "qui",
        "que",
        "quoi",
        "quel",
        "quelle",
        "quels",
        "quelles",
        "comment",
        "combien",
        "pourquoi",
        "quand",
        "dans",
        "sur",
        "sous",
        "par",
        "pour",
        "avec",
        "sans",
        "est",
        "sont",
        "selon",
        "lors",
        "pendant",
        "entre",
        "vers",
        "chez",
        "ce",
        "cet",
        "cette",
        "ces",
        "son",
        "sa",
        "ses",
        "leur",
        "leurs",
        "si",
        "ne",
        "pas",
        "plus",
        "the",
        "a",
        "an",
        "of",
        "to",
        "in",
        "on",
        "for",
        "and",
        "or",
        "who",
        "what",
        "which",
        "how",
        "when",
        "where",
        "why",
        "is",
        "are",
        "does",
        "do",
        "can",
        "may",
        "should",
        "must",
        "by",
        "with",
        "at",
        "from",
        "as",
        "that",
        "this",
        "during",
        "between",
        "under",
        "after",
        "before",
        "it",
        "its",
    ]
)
NUMBER_WORDS = {
    "one": "1", "two": "2", "three": "3", "four": "4", "five": "5", "six": "6", "seven": "7", "eight": "8",
    "nine": "9", "ten": "10", "eleven": "11", "twelve": "12", "fifteen": "15", "twenty": "20", "thirty": "30",
    "forty": "40", "fifty": "50", "sixty": "60", "hundred": "100", "thousand": "1000", "half": "0.5", "twice": "2",
    "double": "2", "single": "1", "both": "2", "first": "1", "second": "2", "third": "3",
}  # fmt: skip


def corpus_pattern(term: str, word: bool = False) -> str:
    """Expression régulière (PostgreSQL `~*`) tolérant les variantes d'écriture : SM-2, SM 2, SM2."""
    core = "[^a-z0-9]{0,2}".join(re.escape(c) for c in re.sub(r"[^a-z0-9]", "", term.lower()))
    return "\\m" + core + "\\M" if word else core


def key_terms(text: str) -> list[str]:
    """Noms propres, sigles et codes d'un texte anglais (la reformulation de la question)."""
    words = re.findall(r"[A-Za-z0-9][A-Za-z0-9\-/]*", text)
    keys = []
    for i, w in enumerate(words):
        if len(w) < 3 or w.lower() in STOPWORDS:
            continue
        code = any(c.isdigit() for c in w) and any(c.isalpha() for c in w)
        sigle = w.isupper() and w.isalpha()
        propre = i > 0 and w[0].isupper() and w[1:].islower() and len(w) >= 4
        if code or sigle or propre:
            keys.append(w)
    return keys


def grounded(
    q: str,
    ans: str,
    cited_src: Iterable[dict[str, Any]],
    enq: str = "",
    *,
    in_corpus: CorpusLookup,
    in_corpus_word: CorpusLookup | None = None,
    word: bool = False,
) -> tuple[bool, str]:
    """-> (ok, raison).
    (1) chaque nombre de la réponse figure dans les extraits cités (en chiffres ou en lettres) ;
    (2) un nom propre, sigle ou code de la question absent de toutes les publications chargées : refus."""
    body = " ".join(x["text"] + " " + (x.get("title") or "") for x in cited_src)
    low = body.lower()
    flat = re.sub(r"[\s\u00a0\u202f,]", "", low)
    present = set(re.findall(r"\d+(?:\.\d+)?", low.replace(",", ""))) | {
        v for w, v in NUMBER_WORDS.items() if re.search(r"\b" + w + r"\b", low)
    }
    present |= set(re.findall(r"\d+(?:\.\d+)?", (q + " " + (enq or "")).replace(",", ".")))
    for a_, b_ in re.findall(
        r"\b(twenty|thirty|forty|fifty|sixty)[- ](one|two|three|four|five|six|seven|eight|nine)\b", low
    ):
        present.add(str(int(NUMBER_WORDS[a_]) + int(NUMBER_WORDS[b_])))
    txt = re.sub(r"\[[\d,\s]+\]", " ", ans)
    for n in re.findall(r"\d+(?:[.,]\d+)?", re.sub(r"(?<=\d)[\s\u00a0\u202f](?=\d{3}\b)", "", txt)):
        v = n.replace(",", ".")
        if len(v) == 1:
            continue  # chiffre isolé (énumération, « 2 conditions ») : non contrôlé
        if (
            v in present
            or n in low
            or v in low
            or v.replace(".", "") in flat
            or n.replace(",", "") in present
            or (v.endswith(".0") and v[:-2] in present)
        ):
            continue
        return False, f"un chiffre de la réponse ({n}) ne figure pas dans les extraits cités"
    ql = q.lower()
    for k in key_terms(enq or ""):
        if k.lower() not in ql:
            continue  # seulement les termes écrits par l'utilisateur, pas ceux ajoutés par la reformulation
        sig = word and k.isupper() and k.isalpha() and len(k) <= 6  # sigle court : mot entier exigé
        if sig:
            if re.search(r"\b" + re.escape(k.lower()) + r"s?\b", low):
                continue
            lookup = in_corpus_word or in_corpus
            if not lookup(k) and not lookup(k.rstrip("s")):
                return False, f"« {k} » n'apparaît dans aucune publication chargée"
            continue
        if (
            k.lower() in low
            or k.lower().rstrip("s") in low
            or re.sub(r"[^a-z0-9]", "", k.lower()) in re.sub(r"[^a-z0-9]", "", low)
        ):
            continue
        if not in_corpus(k) and not in_corpus(k.rstrip("s")):
            return False, f"« {k} » n'apparaît dans aucune publication chargée"
    return True, ""
