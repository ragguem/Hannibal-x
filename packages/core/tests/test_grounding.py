from hannibal_core.grounding import (
    NOT_FOUND_PATTERN,
    corpus_pattern,
    edit_distance,
    grounded,
    key_terms,
    suggest,
)


def test_corpus_pattern_tolerates_spelling_variants() -> None:
    assert corpus_pattern("SM-2") == "s[^a-z0-9]{0,2}m[^a-z0-9]{0,2}2"
    assert corpus_pattern("RAZ", word=True) == "\\mr[^a-z0-9]{0,2}a[^a-z0-9]{0,2}z\\M"


def test_key_terms_and_distance() -> None:
    assert key_terms("Where is the QX-7 of NATO near Toulon and the cat") == ["QX-7", "NATO", "Toulon"]
    assert edit_distance("ZEBAR", "ZEBRA") == 1
    assert edit_distance("", "ABC") == 3


def test_short_acronym_falls_back_to_in_corpus_without_word_lookup() -> None:
    seen: list[str] = []

    def lookup(term: str) -> bool:
        seen.append(term)
        return term == "RAZ"

    ok, _ = grounded("Le RAZ ?", "Rien.", [{"text": "x"}], "The RAZ", in_corpus=lookup, word=True)
    assert ok
    assert seen == ["RAZ"]


def test_suggest_stops_at_n_and_skips_terms_absent_from_publications() -> None:
    abbrs = [("ABD", "a", "a"), ("ABE", "b", "b"), ("ABF", "c", "c"), ("ABG", "d", "d")]
    out = suggest("ABC", abbrs, [], lambda t: t != "ABE", n=2)
    assert [x["terme"] for x in out] == ["ABD", "ABF"]


def test_not_found_pattern() -> None:
    assert NOT_FOUND_PATTERN.search("The publication does not specify it.")
    assert not NOT_FOUND_PATTERN.search("Two lookouts.")
