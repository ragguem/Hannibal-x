from typing import Any

import pytest
from fastapi.testclient import TestClient

from hannibal_doctrine.application.ports import DependencyDown
from hannibal_doctrine.main import create_app
from hannibal_doctrine.socle.composition import build_adapters
from hannibal_doctrine.socle.settings import AnswerStyle, DoctrineAdapters, DoctrineSettings

RESTRICTED = "DEMO-RESTREINT"


def settings(**overrides: Any) -> DoctrineSettings:
    values: dict[str, Any] = {
        "environment": "dev",
        "adapters": DoctrineAdapters.SAMPLE,
        "classified_publications": [RESTRICTED],
        "min_similarity": 0.3,
    }
    return DoctrineSettings(**(values | overrides))


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app(settings()))


def test_cited_answer_from_the_closest_passage(client: TestClient) -> None:
    body = client.post("/ask", json={"question": "What is the standard tactical speed?"}).json()

    assert body["status"] == "answered"
    assert "12 knots" in body["answer"]
    assert [c["article"] for c in body["citations"]] == ["102"]
    assert body["thresholds"]["min_similarity"] == 0.3
    assert body["index_version"].startswith("sample-")


def test_french_question_is_rewritten_before_search(client: TestClient) -> None:
    body = client.post("/ask", json={"question": "Quelle est la vitesse tactique standard ?"}).json()

    assert body["status"] == "answered"
    assert body["query_en"].startswith("quelle est la speed")


def test_question_outside_the_corpus_is_refused(client: TestClient) -> None:
    body = client.post("/ask", json={"question": "Who painted the Mona Lisa?"}).json()

    assert body["status"] == "refused"
    assert body["refusal_reason"] == "no_evidence"
    assert body["citations"] == []


def test_quoted_style_answers_with_an_exact_quote() -> None:
    client = TestClient(create_app(settings(answer_style=AnswerStyle.QUOTES)))

    body = client.post("/ask", json={"question": "Which flag does the delivering ship hoist?"}).json()

    assert body["status"] == "answered"
    assert "ROMEO" in body["answer"]


def test_classified_publication_is_hidden_unless_allowed(client: TestClient) -> None:
    question = {"question": "Where is the silent manoeuvre procedure described?"}

    hidden = client.post("/ask", json=question).json()
    allowed = client.post("/ask", json=question | {"include_classified": True}).json()

    assert hidden["status"] == "refused"
    assert allowed["citations"][0]["publication"] == RESTRICTED
    assert client.get("/publications").json()["publications"] == ["DEMO-MANUEL"]
    assert RESTRICTED in client.get("/publications?include_classified=true").json()["publications"]


def test_glossary_lookup_by_abbreviation(client: TestClient) -> None:
    entries = client.get("/glossary?q=ras").json()["entries"]

    assert entries[0]["fr"] == "ravitaillement à la mer"


def test_explanation_falls_back_to_the_deterministic_reading(client: TestClient) -> None:
    body = client.post(
        "/explain",
        json={
            "message": "CORPEN 090",
            "meaning_en": "Turn in succession to course 090.",
            "meaning_fr": "Changer de cap en succession au 090.",
            "parameters": {"course": 90},
        },
    ).json()

    assert body["source"] in {"checked_model", "deterministic"}
    assert body["explanation_en"]


def test_ollama_down_answers_503() -> None:
    adapters = build_adapters(settings())

    class DownChat:
        default_model = "down"

        async def chat(self, *args: Any, **kwargs: Any) -> str:
            raise DependencyDown("ollama", "connexion refusée")

    class DownEmbedder:
        model_name = "down"

        async def embed(self, text: str) -> list[float]:
            raise DependencyDown("ollama", "connexion refusée")

    broken = type(adapters)(adapters.index, adapters.glossary, DownEmbedder(), DownChat(), adapters.reranker)
    response = TestClient(create_app(settings(), broken)).post("/ask", json={"question": "Formation speed?"})

    assert response.status_code == 503
    assert response.json()["code"] == "dependency_unavailable"


def test_real_mode_requires_a_database_url() -> None:
    with pytest.raises(RuntimeError, match="HX_DOCTRINE_DATABASE_URL"):
        build_adapters(settings(adapters=DoctrineAdapters.REAL, database_url=None))
