from collections.abc import Sequence

from fastapi.testclient import TestClient

from hannibal_rerank.main import create_app
from hannibal_rerank.socle.settings import RerankSettings, ScorerKind

TOKEN = "jeton-interne-de-test"


class LengthScorer:
    """Score = longueur du passage, divisée par la longueur de la question : l'ordre se lit facilement."""

    model_name = "length"

    def __init__(self) -> None:
        self.calls = 0

    def score(self, pairs: Sequence[tuple[str, str]]) -> list[float]:
        self.calls += 1
        return [len(passage) / len(query) for query, passage in pairs]


def client(scorer: object | None = None, *, max_passage_chars: int = 4000) -> TestClient:
    settings = RerankSettings(  # type: ignore[call-arg]
        scorer=ScorerKind.LEXICAL, internal_token=TOKEN, max_passage_chars=max_passage_chars
    )
    return TestClient(create_app(settings, scorer=scorer), headers={"X-Internal-Token": TOKEN})  # type: ignore[arg-type]


def test_lexical_scorer_prefers_the_passage_that_shares_the_question_words() -> None:
    response = client().post(
        "/rerank",
        json={
            "queries": ["replenishment at sea approach speed"],
            "passages": ["Station keeping in column.", "The approach speed during replenishment at sea…"],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["model"] == "lexical-overlap"
    assert body["scores"][1] > body["scores"][0]


def test_each_passage_keeps_its_best_score_over_the_queries() -> None:
    scorer = LengthScorer()
    response = client(scorer).post(
        "/rerank", json={"queries": ["long question", "q"], "passages": ["ab", "abcd"]}
    )
    assert response.json()["scores"] == [2.0, 4.0]
    assert scorer.calls == 2


def test_passages_are_truncated_before_scoring() -> None:
    response = client(LengthScorer(), max_passage_chars=100).post(
        "/rerank", json={"queries": ["q"], "passages": ["x" * 500]}
    )
    assert response.json()["scores"] == [100.0]


def test_requires_the_internal_token() -> None:
    settings = RerankSettings(scorer=ScorerKind.LEXICAL, internal_token=TOKEN)  # type: ignore[call-arg]
    response = TestClient(create_app(settings)).post("/rerank", json={"queries": ["q"], "passages": ["p"]})
    assert response.status_code == 401


def test_rejects_an_empty_query_list() -> None:
    assert client().post("/rerank", json={"queries": [], "passages": ["p"]}).status_code == 422
