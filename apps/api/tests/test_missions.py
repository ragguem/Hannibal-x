import asyncio
from typing import Any

import pytest
from fastapi.testclient import TestClient

from hannibal_api.application.dispatch import Dispatcher
from hannibal_api.application.missions import Missions
from hannibal_api.infrastructure.fleet import InMemoryFleet
from hannibal_api.infrastructure.persistence.memory import InMemoryCommandStore
from hannibal_api.socle.container import Container
from hannibal_api.socle.main import create_app
from hannibal_api.socle.openapi import OPENAPI_FILE, render
from hannibal_api.socle.settings import AdapterMode, ApiSettings

RUNNER_PERIOD_S = 0.5
FLEET = {"hannibal", "alfa", "charlie", "delta"}


class ManualClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


class MissionHarness:
    """API en mode `fake` et horloge avancée à la main : le test déclenche chaque pas du `MissionRunner`."""

    def __init__(self, **settings_overrides: object) -> None:
        settings = ApiSettings(
            **{
                "adapters": AdapterMode.FAKE,
                "log_json": True,
                "mission_runner_period_s": 0,
                "dispatch_poll_period_s": 0,
                **settings_overrides,
            }  # type: ignore[arg-type]
        )
        self.clock = ManualClock()
        container = Container(settings=settings)
        container.clock.override(self.clock)
        self.client = TestClient(create_app(settings, container), raise_server_exceptions=False)
        self.missions: Missions = container.missions()
        self.dispatcher: Dispatcher = container.dispatcher()
        self.fleet: InMemoryFleet = container.fleet()
        self.command_store: InMemoryCommandStore = container.command_store()

    def dispatch_next(self) -> bool:
        return asyncio.run(self.dispatcher.dispatch_next())

    def start(self, **body: Any) -> dict[str, Any]:
        response = self.client.post(
            "/v1/missions", json={"scenario_id": "contact_inconnu", "player_ship": "hannibal", **body}
        )
        assert response.status_code == 201, response.text
        return dict(response.json())

    def read(self, mission_id: str) -> dict[str, Any]:
        return dict(self.client.get(f"/v1/missions/{mission_id}").json())

    def advance(self, mission_id: str, seconds: float) -> None:
        for _ in range(int(seconds / RUNNER_PERIOD_S)):
            self.clock.now += RUNNER_PERIOD_S
            asyncio.run(self.missions.advance(mission_id))


@pytest.fixture
def harness() -> MissionHarness:
    return MissionHarness()


def test_list_scenarios(harness: MissionHarness) -> None:
    scenarios = harness.client.get("/v1/scenarios").json()
    assert len(scenarios) == 6
    unknown_contact = next(s for s in scenarios if s["id"] == "contact_inconnu")
    assert unknown_contact["guide_ship"] == "hannibal"
    assert unknown_contact["playable_ships"][0] == "hannibal"


def test_mission_runs_end_to_end_without_screen(harness: MissionHarness) -> None:
    mission = harness.start()
    assert mission["phase"] == "running"
    assert {ship["name"] for ship in mission["ships"]} == FLEET

    harness.advance(mission["id"], 40)
    mission = harness.read(mission["id"])
    assert [contact["id"] for contact in mission["contacts"]] == ["TRK017"]
    assert mission["ships"][0]["speed_mps"] > 0

    outcome = harness.client.post(
        f"/v1/missions/{mission['id']}/orders", json={"text": "ALL SHIPS TURN 30 STBD"}
    )
    assert outcome.json()["accepted"] is True
    assert outcome.json()["text_en"].startswith("ALL SHIPS THIS IS HANNIBAL")

    classification = harness.client.post(
        f"/v1/missions/{mission['id']}/contacts/TRK017/classification", json={"classification": "neutre"}
    )
    assert classification.status_code == 204

    harness.advance(mission["id"], 420)
    mission = harness.read(mission["id"])
    assert mission["phase"] == "ended"
    assert mission["debrief"]["objectives_total"] == len(mission["objectives"])
    assert mission["debrief"]["classification_by_contact"]["TRK017"] == {
        "chosen": "neutre",
        "actual": "neutre",
    }

    late_order = harness.client.post(
        f"/v1/missions/{mission['id']}/orders", json={"text": "ALL SHIPS TURN 30 STBD"}
    )
    assert late_order.status_code == 409
    assert late_order.json()["code"] == "mission_ended"


def test_refused_order_carries_reason(harness: MissionHarness) -> None:
    mission = harness.start()
    outcome = harness.client.post(f"/v1/missions/{mission['id']}/orders", json={"text": "BONJOUR"}).json()
    assert outcome["accepted"] is False
    assert outcome["refusal_reason"]


def test_simulate_order_and_recommend(harness: MissionHarness) -> None:
    mission = harness.start()
    harness.advance(mission["id"], 40)
    simulations = f"/v1/missions/{mission['id']}/simulations"
    simulation = harness.client.post(simulations, json={"text": "ALL SHIPS TURN 30 STBD"}).json()
    assert simulation["accepted"] is True
    assert set(simulation["track_by_ship"]) == FLEET
    assert simulation["contact_cpas"][0]["contact_id"] == "TRK017"
    nothing_to_simulate = harness.client.post(simulations, json={"text": "ALL SHIPS ROGER"}).json()
    assert nothing_to_simulate["accepted"] is False
    recommendations = harness.client.get(f"/v1/missions/{mission['id']}/recommendations").json()
    assert recommendations
    assert {"kind", "text", "reason"} <= recommendations[0].keys()


def test_helm_requires_manual_mode(harness: MissionHarness) -> None:
    mission = harness.start()
    response = harness.client.post(f"/v1/missions/{mission['id']}/helm", json={"course_deg": 90})
    assert response.status_code == 409
    assert response.json()["code"] == "manual_helm_inactive"


def test_manual_helm(harness: MissionHarness) -> None:
    mission = harness.start(player_ship="alfa", manual_helm=True)
    helm = harness.client.post(
        f"/v1/missions/{mission['id']}/helm", json={"course_deg": 370, "speed_change_kn": 2}
    ).json()
    assert helm == {"course_deg": 10.0, "speed_kn": 14.0, "rudder": 0}


def test_autopilot_and_reply_without_request(harness: MissionHarness) -> None:
    mission = harness.start(player_ship="alfa")
    assert (
        harness.client.put(f"/v1/missions/{mission['id']}/autopilot", json={"enabled": True}).status_code
        == 204
    )
    assert harness.read(mission["id"])["autopilot"] is True
    reply = harness.client.post(
        f"/v1/missions/{mission['id']}/requests/charlie/reply", json={"approve": True}
    )
    assert reply.status_code == 404
    assert reply.json()["code"] == "request_not_found"


def test_refusals_carry_stable_codes(harness: MissionHarness) -> None:
    client = harness.client
    unknown_scenario = client.post("/v1/missions", json={"scenario_id": "nope", "player_ship": "x"})
    assert unknown_scenario.json()["code"] == "scenario_not_found"
    unknown_ship = client.post("/v1/missions", json={"scenario_id": "contact_inconnu", "player_ship": "x"})
    assert unknown_ship.json()["code"] == "ship_not_found"
    assert client.get("/v1/missions/nope").json()["code"] == "mission_not_found"

    mission = harness.start()
    second = client.post("/v1/missions", json={"scenario_id": "contact_inconnu", "player_ship": "alfa"})
    assert second.status_code == 409
    unknown_contact = client.post(
        f"/v1/missions/{mission['id']}/contacts/TRK999/classification", json={"classification": "ami"}
    )
    assert unknown_contact.json()["code"] == "contact_not_found"
    assert client.post(f"/v1/missions/{mission['id']}/orders", json={"text": ""}).status_code == 422

    assert client.delete(f"/v1/missions/{mission['id']}").status_code == 204
    assert harness.read(mission["id"])["phase"] == "ended"
    harness.start()


def test_real_mode_without_sim_bridge() -> None:
    harness = MissionHarness(adapters=AdapterMode.REAL)
    response = harness.client.post(
        "/v1/missions", json={"scenario_id": "contact_inconnu", "player_ship": "hannibal"}
    )
    assert response.status_code == 503
    assert response.json()["dependency"] == "sim-bridge"


def test_internal_token_required_when_configured() -> None:
    client = MissionHarness(internal_token="s3cret").client
    assert client.get("/v1/scenarios").status_code == 401
    assert client.get("/v1/scenarios", headers={"X-Internal-Token": "s3cret"}).status_code == 200


def test_runner_advances_missions_by_itself() -> None:
    settings = ApiSettings(adapters=AdapterMode.FAKE, log_json=True, mission_runner_period_s=0.01)  # type: ignore[call-arg]
    with TestClient(create_app(settings)) as client:
        body = {"scenario_id": "contact_inconnu", "player_ship": "hannibal"}
        mission_id = client.post("/v1/missions", json=body).json()["id"]

        def guide_speed() -> float:
            return float(client.get(f"/v1/missions/{mission_id}").json()["ships"][0]["speed_mps"])

        for _ in range(200):
            if guide_speed() > 0:
                break
            asyncio.run(asyncio.sleep(0.01))
        assert guide_speed() > 0


def test_actions_are_audited_with_their_author(harness: MissionHarness) -> None:
    alice = {"X-Hx-User": "alice"}
    mission = harness.client.post(
        "/v1/missions", json={"scenario_id": "contact_inconnu", "player_ship": "hannibal"}, headers=alice
    ).json()
    harness.advance(mission["id"], 40)
    harness.client.post(
        f"/v1/missions/{mission['id']}/orders", json={"text": "ALL SHIPS TURN 30 STBD"}, headers=alice
    )
    harness.client.post(f"/v1/missions/{mission['id']}/orders", json={"text": "BONJOUR"}, headers=alice)
    harness.client.post(
        f"/v1/missions/{mission['id']}/contacts/TRK017/classification",
        json={"classification": "hostile"},
        headers=alice,
    )
    harness.advance(mission["id"], 420)

    page = harness.client.get("/v1/audit", params={"mission_id": mission["id"]}).json()
    assert [(event["event"], event["actor_id"]) for event in page["events"]] == [
        ("mission_started", "alice"),
        ("approved", "alice"),
        ("contact_classified", "alice"),
        ("mission_finished", None),
    ]
    assert page["next_after_seq"] is None
    assert harness.client.get("/v1/audit", params={"limit": 2}).json()["next_after_seq"] == 2
    assert harness.client.get("/v1/audit", params={"mission_id": "pas-un-uuid"}).status_code == 422
    assert harness.client.get("/v1/audit/integrity").json()["checked_events"] == 4


def test_events_stream_ends_with_phase(harness: MissionHarness) -> None:
    mission = harness.start()
    harness.client.delete(f"/v1/missions/{mission['id']}")
    with harness.client.stream("GET", f"/v1/missions/{mission['id']}/events") as response:
        assert response.headers["content-type"].startswith("text/event-stream")
        body = response.read().decode()
    events = [block.split("\n") for block in body.strip().split("\n\n")]
    assert [lines[0] for lines in events] == ["event: situation", "event: phase"]
    assert '"phase":"ended"' in events[0][1]
    assert events[1][1] == 'data: {"phase": "ended"}'


TURN_ORDER = "ALL SHIPS TURN 30 STBD"
UNKNOWN_ID = "00000000-0000-4000-8000-000000000000"


def submit_for_review(harness: MissionHarness, **body: Any) -> tuple[str, dict[str, Any]]:
    mission = harness.start()
    harness.advance(mission["id"], 40)
    outcome = harness.client.post(
        f"/v1/missions/{mission['id']}/orders",
        json={"text": TURN_ORDER, "mode": "review", **body},
        headers={"X-Hx-User": "alice"},
    ).json()
    return mission["id"], outcome


def decide(harness: MissionHarness, command_id: str, decision: str) -> Any:
    return harness.client.post(
        f"/v1/commands/{command_id}/decision", json={"decision": decision}, headers={"X-Hx-User": "bob"}
    )


def player_radio_count(harness: MissionHarness, mission_id: str) -> int:
    messages = harness.client.get(f"/v1/missions/{mission_id}").json()["radio_messages"]
    return sum(message["kind"] == "joueur" for message in messages)


def test_reviewed_order_is_applied_only_once_dispatched(harness: MissionHarness) -> None:
    mission_id, outcome = submit_for_review(harness)
    assert outcome["accepted"] is True
    assert outcome["command_state"] == "awaiting_review"
    assert player_radio_count(harness, mission_id) == 0

    response = decide(harness, outcome["command_id"], "approve")
    assert response.status_code == 202
    assert response.json()["state"] == "dispatching"
    assert response.json()["decided_by"] == "bob"
    assert player_radio_count(harness, mission_id) == 0

    assert harness.dispatch_next() is True
    assert harness.dispatch_next() is False
    command = harness.client.get(f"/v1/commands/{outcome['command_id']}").json()
    assert command["state"] == "dispatched"
    assert outcome["command_id"] in harness.fleet.maneuver_by_command
    assert player_radio_count(harness, mission_id) == 1

    audit = harness.client.get("/v1/audit", params={"mission_id": mission_id}).json()["events"]
    assert [(event["event"], event["command_id"]) for event in audit if event["command_id"]] == [
        ("awaiting_review", outcome["command_id"]),
        ("approved", outcome["command_id"]),
        ("simulator_dispatched", outcome["command_id"]),
    ]


def test_rejected_order_is_never_sent(harness: MissionHarness) -> None:
    mission_id, outcome = submit_for_review(harness)
    assert decide(harness, outcome["command_id"], "reject").json()["state"] == "rejected"
    second = decide(harness, outcome["command_id"], "approve")
    assert second.status_code == 409
    assert second.json()["code"] == "decision_not_allowed"
    assert harness.dispatch_next() is False
    assert harness.fleet.dispatch_calls == 0
    assert player_radio_count(harness, mission_id) == 0


def test_invalid_order_creates_no_command(harness: MissionHarness) -> None:
    mission = harness.start()
    outcome = harness.client.post(
        f"/v1/missions/{mission['id']}/orders", json={"text": "BONJOUR", "mode": "review"}
    ).json()
    assert outcome["accepted"] is False
    assert outcome["command_id"] is None
    assert harness.client.get(f"/v1/commands/{UNKNOWN_ID}").status_code == 404


def test_transient_failure_is_retried_without_double_execution(harness: MissionHarness) -> None:
    mission_id, outcome = submit_for_review(harness)
    decide(harness, outcome["command_id"], "approve")
    harness.fleet.failures_before_success = 1

    assert harness.dispatch_next() is True
    command = harness.client.get(f"/v1/commands/{outcome['command_id']}").json()
    assert command["state"] == "dispatching"
    assert command["last_error"] == "sim-bridge injoignable"
    assert harness.dispatch_next() is False

    harness.clock.now += 1.0
    assert harness.dispatch_next() is True
    assert harness.client.get(f"/v1/commands/{outcome['command_id']}").json()["state"] == "dispatched"
    assert harness.fleet.dispatch_calls == 2
    assert player_radio_count(harness, mission_id) == 1


def test_failed_dispatch_can_be_retried_until_its_deadline() -> None:
    harness = MissionHarness(dispatch_max_attempts=1, command_validity_s=30)
    _, outcome = submit_for_review(harness)
    decide(harness, outcome["command_id"], "approve")
    harness.fleet.failures_before_success = 1
    harness.dispatch_next()
    command = harness.client.get(f"/v1/commands/{outcome['command_id']}").json()
    assert command["state"] == "dispatch_failed"
    assert command["last_error"].startswith("attempts_exhausted")

    assert decide(harness, outcome["command_id"], "retry").json()["state"] == "dispatching"
    harness.dispatch_next()
    assert harness.client.get(f"/v1/commands/{outcome['command_id']}").json()["state"] == "dispatched"


def test_expired_order_is_not_sent() -> None:
    harness = MissionHarness(command_validity_s=30)
    _, outcome = submit_for_review(harness)
    decide(harness, outcome["command_id"], "approve")
    harness.clock.now += 31
    harness.dispatch_next()
    command = harness.client.get(f"/v1/commands/{outcome['command_id']}").json()
    assert command["state"] == "dispatch_failed"
    assert command["last_error"] == "deadline_passed"
    assert harness.fleet.dispatch_calls == 0
    retry = decide(harness, outcome["command_id"], "retry")
    assert retry.status_code == 409
    assert retry.json()["code"] == "command_expired"


@pytest.mark.parametrize(
    ("already_executed", "expected_state"), [(True, "dispatched"), (False, "dispatching")]
)
def test_restart_reconciles_dispatches_left_in_flight(
    harness: MissionHarness, already_executed: bool, expected_state: str
) -> None:
    _, outcome = submit_for_review(harness)
    decide(harness, outcome["command_id"], "approve")
    claimed = asyncio.run(harness.command_store.claim_next())
    assert claimed is not None
    if already_executed:
        asyncio.run(harness.fleet.dispatch(claimed.command_id, claimed.maneuver))

    asyncio.run(harness.dispatcher.reconcile())

    assert harness.client.get(f"/v1/commands/{outcome['command_id']}").json()["state"] == expected_state
    assert harness.dispatch_next() is not already_executed
    assert harness.client.get(f"/v1/commands/{outcome['command_id']}").json()["state"] == "dispatched"
    assert harness.fleet.dispatch_calls == 1


def test_openapi_file_is_up_to_date() -> None:
    assert OPENAPI_FILE.read_text(encoding="utf-8") == render(), "relancer `uv run hx-export-openapi`"
