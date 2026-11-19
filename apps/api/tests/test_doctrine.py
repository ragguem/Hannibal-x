"""`QueryDoctrine`, `SearchGlossary`, `ExplainCommand` en mode `fake` (assistant d'exemple, texte inventé)."""

import asyncio
import json
import uuid

import httpx
import pytest
from fastapi.testclient import TestClient

from hannibal_api.application.doctrine import DoctrineBusy, GpuGate
from hannibal_api.domain.commands import Command, CommandState
from hannibal_api.domain.doctrine import order_parameters
from hannibal_api.infrastructure.doctrine import DoctrineClient, SampleDoctrine
from hannibal_api.infrastructure.persistence.memory import InMemoryDoctrineTraceStore
from hannibal_api.socle.container import Container
from hannibal_api.socle.main import create_app
from hannibal_api.socle.settings import AdapterMode, ApiSettings
from hannibal_contracts.doctrine import AskRequest
from hannibal_platform.errors import DependencyUnavailable

OPERATOR = {"X-Hx-User": "alice", "X-Hx-Permissions": "doctrine:ask,glossary:read"}
SUPERVISOR = {"X-Hx-User": "bob", "X-Hx-Permissions": "doctrine:ask,glossary:read,doctrine:classified"}


class DoctrineHarness:
    def __init__(self) -> None:
        settings = ApiSettings(
            adapters=AdapterMode.FAKE, log_json=True, mission_runner_period_s=0, dispatch_poll_period_s=0
        )  # type: ignore[call-arg]
        self.container = Container(settings=settings)
        self.client = TestClient(create_app(settings, self.container), raise_server_exceptions=False)
        self.doctrine: SampleDoctrine = self.container.doctrine()
        self.traces: InMemoryDoctrineTraceStore = self.container.doctrine_traces()


@pytest.fixture
def harness() -> DoctrineHarness:
    return DoctrineHarness()


def test_answer_is_traced_and_audited(harness: DoctrineHarness) -> None:
    response = harness.client.post(
        "/v1/doctrine/questions", json={"question": "Quelle est la vitesse tactique ?"}, headers=OPERATOR
    )

    body = response.json()
    assert response.status_code == 200
    assert body["status"] == "answered"
    assert body["citations"][0]["article"] == "102"
    [trace] = harness.traces.traces
    assert trace.id == body["trace_id"]
    assert trace.actor_id == "alice"
    assert trace.cited == [{"number": 1, "passage_id": 2, "publication": "DEMO-MANUEL"}]
    events = [r.event for r in harness.container.in_memory_journal().audit]
    assert events == ["doctrine_answered"]


def test_refusal_is_audited_with_its_reason(harness: DoctrineHarness) -> None:
    body = harness.client.post(
        "/v1/doctrine/questions", json={"question": "Qui a peint la Joconde ?"}, headers=OPERATOR
    ).json()

    assert body["refusal_reason"] == "no_evidence"
    [record] = harness.container.in_memory_journal().audit
    assert record.event == "doctrine_refused"
    assert record.payload["refusal_reason"] == "no_evidence"


def test_classified_publications_need_the_permission(harness: DoctrineHarness) -> None:
    question = {"question": "Vitesse ?", "publication": "DEMO-RESTREINT"}

    refused = harness.client.post("/v1/doctrine/questions", json=question, headers=OPERATOR)
    allowed = harness.client.post("/v1/doctrine/questions", json=question, headers=SUPERVISOR)

    assert refused.status_code == 403
    assert refused.json()["code"] == "publication_not_allowed"
    assert allowed.status_code == 200
    assert harness.doctrine.requests[-1] == AskRequest(
        question="Vitesse ?", publications=["DEMO-RESTREINT"], include_classified=True
    )
    operator_view = harness.client.get("/v1/doctrine/publications", headers=OPERATOR).json()
    assert operator_view["publications"] == ["DEMO-MANUEL"]


def test_operator_questions_never_search_classified_publications(harness: DoctrineHarness) -> None:
    harness.client.post("/v1/doctrine/questions", json={"question": "Vitesse ?"}, headers=OPERATOR)

    assert harness.doctrine.requests[-1].include_classified is False


def test_glossary_search(harness: DoctrineHarness) -> None:
    body = harness.client.get("/v1/glossary", params={"q": "RAS"}).json()

    assert body["entries"][0]["fr"] == "ravitaillement à la mer"


def test_command_explanation_uses_the_decoded_values(harness: DoctrineHarness) -> None:
    command_id = str(uuid.uuid4())
    command = Command(
        id=command_id,
        mission_id=str(uuid.uuid4()),
        text="ALL SHIPS CORPEN 045",
        maneuver={
            "to": ["TOUS"],
            "orders": [{"type": "CORPEN", "cap": 45}],
            "en": "All ships: course 045.",
            "fr": "Tous : cap 045.",
        },
        state=CommandState.AWAITING_REVIEW,
        submitted_by="alice",
    )
    asyncio.run(harness.container.command_store().create(command, []))

    body = harness.client.post(f"/v1/commands/{command_id}/explanation").json()

    assert body["command_id"] == command_id
    assert body["explanation_fr"] == "Tous : cap 045."


def test_unknown_command_cannot_be_explained(harness: DoctrineHarness) -> None:
    response = harness.client.post(f"/v1/commands/{uuid.uuid4()}/explanation")

    assert response.status_code == 404


def test_order_parameters_keep_side_course_and_speed() -> None:
    orders = [{"type": "TURN", "side": "STBD", "deg": 30}, {"type": "SPEED", "kn": 12}]

    assert order_parameters(orders) == {"relative_degrees": 30, "side": "STBD", "speed_knots": 12}


async def test_gate_refuses_beyond_the_waiting_line() -> None:
    gate = GpuGate(active=1, waiting=1, wait_s=5)
    release = asyncio.Event()

    async def hold() -> None:
        async with gate.slot():
            await release.wait()

    first = asyncio.create_task(hold())
    await asyncio.sleep(0)
    second = asyncio.create_task(hold())
    await asyncio.sleep(0)
    with pytest.raises(DoctrineBusy):
        async with gate.slot():
            pass
    release.set()
    await asyncio.gather(first, second)


async def test_gate_gives_up_after_the_wait() -> None:
    gate = GpuGate(active=1, waiting=2, wait_s=0.05)
    async with gate.slot():
        with pytest.raises(DoctrineBusy):
            async with gate.slot():
                pass


async def test_client_turns_service_errors_into_unavailable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/publications":
            return httpx.Response(200, content=json.dumps({"publications": ["DEMO-MANUEL"]}))
        return httpx.Response(503)

    client = DoctrineClient("http://doctrine", token="t", timeout_s=1, transport=httpx.MockTransport(handler))
    assert await client.publications(include_classified=False) == ["DEMO-MANUEL"]
    with pytest.raises(DependencyUnavailable):
        await client.ask(AskRequest(question="Vitesse ?"))
    await client.aclose()
