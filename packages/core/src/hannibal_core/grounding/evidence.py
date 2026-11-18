"""Termes inconnus, propositions « vouliez-vous dire ? » et motifs de refus, sans modèle.

Repris de legacy/v2/scripts/hx2_service_c.py (`_dl`, `suggest`, `add_suggestions`, `NONE`). On ne corrige jamais
en silence : on propose des termes du glossaire présents dans les publications, l'opérateur choisit.
"""

import difflib
import re
from collections.abc import Callable, Sequence
from typing import Any

from hannibal_core.grounding.guard import CorpusLookup, key_terms

Candidate = tuple[str, str, str]  # (terme, anglais, français)

NO_ANSWER = {
    "fr": "Aucune des publications chargées ne répond à cette question.",
    "en": "None of the loaded publications answers this question.",
}
REFUSAL_REASONS = {
    "no_passage": "aucun passage assez proche",
    "unreadable": "réponse du modèle illisible",
    "not_found": "le modèle ne trouve pas la réponse dans les extraits",
    "no_quote": "aucune citation exacte à l'appui",
    "check": "contrôle : ",
    "verification": "vérification : ",
}
NOT_FOUND_PATTERN = re.compile(
    r"(does|do|did) not (specify|mention|state|provide|indicate)|not specified"
    r"|ne (précise|mentionne|spécifie|indique) pas|aucune information",
    re.I,
)


def edit_distance(a: str, b: str) -> int:
    """Distance d'édition avec transposition de deux lettres voisines."""
    la, lb = len(a), len(b)
    m = [[0] * (lb + 1) for _ in range(la + 1)]
    for i in range(la + 1):
        m[i][0] = i
    for j in range(lb + 1):
        m[0][j] = j
    for i in range(1, la + 1):
        for j in range(1, lb + 1):
            c = 0 if a[i - 1] == b[j - 1] else 1
            m[i][j] = min(m[i - 1][j] + 1, m[i][j - 1] + 1, m[i - 1][j - 1] + c)
            if i > 1 and j > 1 and a[i - 1] == b[j - 2] and a[i - 2] == b[j - 1]:
                m[i][j] = min(m[i][j], m[i - 2][j - 2] + 1)
    return m[la][lb]


def suggest(
    term: str,
    abbrs: Sequence[Candidate],
    words: Sequence[Candidate],
    in_corpus_word: CorpusLookup,
    n: int = 3,
) -> list[dict[str, str]]:
    """Termes proches (sigles du glossaire, ou mots), présents dans les publications."""
    t = term.strip()
    up = t.upper()
    out: list[tuple[float, str, str, str]] = []
    if t.isupper() or any(c.isdigit() for c in t) or len(t) <= 5:
        lim = 1 if len(up) <= 4 else 2
        for a, en, fr in abbrs:
            if abs(len(a) - len(up)) > lim:
                continue
            dd = edit_distance(up, a.upper())
            if 0 < dd <= lim:
                out.append((dd, a, en, fr))
    else:
        for w, en, fr in words:
            r = difflib.SequenceMatcher(None, t.lower(), w.lower()).ratio()
            if 0.8 <= r < 1:
                out.append((1 - r, w, en, fr))
    out.sort(key=lambda x: (x[0], x[1]))
    seen: set[str] = set()
    res = []
    for _, a, en, fr in out[:25]:
        if a.upper() in seen or not in_corpus_word(a):
            continue
        seen.add(a.upper())
        res.append({"terme": a, "en": en, "fr": fr})
        if len(res) >= n:
            break
    return res


def unknown_terms(
    q: str,
    query_en: str,
    *,
    in_corpus: CorpusLookup,
    in_corpus_word: CorpusLookup,
    suggest_for: Callable[[str], list[dict[str, str]]],
) -> dict[str, Any]:
    """Termes de la question inconnus des publications (mot entier) et propositions proches.
    -> {"termes_inconnus": [...], "suggestions": [...]} (clés absentes si vides)."""
    ql = q.lower()
    unk: list[str] = []
    sig = [
        w
        for w in re.findall(r"[A-Za-z0-9][A-Za-z0-9\-/]*", q)
        if len(w) >= 3
        and ((w.isupper() and w.isalpha()) or (any(c.isdigit() for c in w) and any(c.isalpha() for c in w)))
    ]
    for k in key_terms(query_en or "") + sig:
        if k.lower() not in ql or k in unk:
            continue
        if (
            in_corpus_word(k)
            or in_corpus_word(k.rstrip("s"))
            or (len(k) >= 7 and k.isalpha() and in_corpus(k[:-2]))
        ):
            continue
        unk.append(k)
    prop = [{"inconnu": k, "propositions": suggest_for(k)} for k in unk[:3]]
    prop = [p for p in prop if p["propositions"]]
    out: dict[str, Any] = {}
    if unk:
        out["termes_inconnus"] = unk
    if prop:
        out["suggestions"] = prop
    return out
