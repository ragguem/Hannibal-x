import asyncio
from typing import Any

import pytest
from fastapi.testclient import TestClient

from hannibal_api.application.missions import Missions
from hannibal_api.socle.container import Container
from hannibal_api.socle.main import create_app
from hannibal_api.socle.openapi import OPENAPI_FILE, render
from hannibal_api.socle.settings import AdapterMode, ApiSettings


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def app_client(**overrides: object) -> tuple[TestClient, Missions, Clock]:
    settings = ApiSettings(
        **{"adapters": AdapterMode.FAKE, "log_json": True, "mission_tick_s": 0, **overrides}
    )  # type: ignore[arg-type]
    clock = Clock()
    container = Container(settings=settings)
    container.clock.override(clock)
    app = create_app(settings, container)
    return TestClient(app, raise_server_exceptions=False), container.missions(), clock


@pytest.fixture
def api() -> tuple[TestClient, Missions, Clock]:
    return app_client()


def start(client: TestClient, **body: Any) -> dict[str, Any]:
    r = client.post("/v1/missions", json={"scenario_id": "contact_inconnu", "player": "hannibal", **body})
    assert r.status_code == 201, r.text
    return dict(r.json())


def advance(missions: Missions, clock: Clock, mission_id: str, seconds: float) -> None:
    for _ in range(int(seconds / 0.5)):
        clock.now += 0.5
        asyncio.run(missions.step(mission_id))


def test_list_scenarios(api: tuple[TestClient, Missions, Clock]) -> None:
    client, _, _ = api
    body = client.get("/v1/scenarios").json()
    assert len(body) == 6
    sc = next(s for s in body if s["id"] == "contact_inconnu")
    assert sc["guide"] == "hannibal"
    assert sc["ships"][0] == "hannibal"


def test_mission_runs_end_to_end_without_screen(api: tuple[TestClient, Missions, Clock]) -> None:
    client, missions, clock = api
    m = start(client)
    assert m["phase"] == "running"
    assert {s["name"] for s in m["ships"]} == {"hannibal", "alfa", "charlie", "delta"}

    advance(missions, clock, m["id"], 40)
    m = client.get(f"/v1/missions/{m['id']}").json()
    assert [c["id"] for c in m["contacts"]] == ["TRK017"]
    assert m["ships"][0]["speed_mps"] > 0

    r = client.post(f"/v1/missions/{m['id']}/orders", json={"text": "ALL SHIPS TURN 30 STBD"})
    assert r.json()["accepted"] is True
    assert r.json()["en"].startswith("ALL SHIPS THIS IS HANNIBAL")

    assert (
        client.post(
            f"/v1/missions/{m['id']}/contacts/TRK017/classification", json={"classification": "neutre"}
        ).status_code
        == 204
    )

    advance(missions, clock, m["id"], 420)
    m = client.get(f"/v1/missions/{m['id']}").json()
    assert m["phase"] == "ended"
    assert m["debrief"]["total"] == len(m["objectives"])
    assert m["debrief"]["classifications"]["TRK017"] == {"chosen": "neutre", "actual": "neutre"}

    r = client.post(f"/v1/missions/{m['id']}/orders", json={"text": "ALL SHIPS TURN 30 STBD"})
    assert r.status_code == 409
    assert r.json()["code"] == "mission_ended"


def test_rejected_order_carries_reason(api: tuple[TestClient, Missions, Clock]) -> None:
    client, _, _ = api
    m = start(client)
    body = client.post(f"/v1/missions/{m['id']}/orders", json={"text": "BONJOUR"}).json()
    assert body["accepted"] is False
    assert body["error"]


def test_simulate_and_recommend(api: tuple[TestClient, Missions, Clock]) -> None:
    client, missions, clock = api
    m = start(client)
    advance(missions, clock, m["id"], 40)
    sim = client.post(f"/v1/missions/{m['id']}/simulations", json={"text": "ALL SHIPS TURN 30 STBD"}).json()
    assert sim["accepted"] is True
    assert set(sim["paths"]) == {"hannibal", "alfa", "charlie", "delta"}
    assert sim["cpa"][0]["contact"] == "TRK017"
    nothing = client.post(f"/v1/missions/{m['id']}/simulations", json={"text": "ALL SHIPS ROGER"}).json()
    assert nothing["accepted"] is False
    recos = client.get(f"/v1/missions/{m['id']}/recommendations").json()
    assert recos
    assert {"kind", "text", "reason"} <= recos[0].keys()


def test_helm_requires_manual_mode(api: tuple[TestClient, Missions, Clock]) -> None:
    client, _, _ = api
    m = start(client)
    r = client.post(f"/v1/missions/{m['id']}/helm", json={"course": 90})
    assert r.status_code == 409
    assert r.json()["code"] == "manual_helm_inactive"


def test_manual_helm(api: tuple[TestClient, Missions, Clock]) -> None:
    client, _, _ = api
    m = start(client, player="alfa", manual=True)
    h = client.post(f"/v1/missions/{m['id']}/helm", json={"course": 370, "speed_delta": 2}).json()
    assert h == {"course": 10.0, "speed_kn": 14.0, "rudder": 0}


def test_autopilot_and_reply(api: tuple[TestClient, Missions, Clock]) -> None:
    client, _, _ = api
    m = start(client, player="alfa")
    assert client.put(f"/v1/missions/{m['id']}/autopilot", json={"enabled": True}).status_code == 204
    assert client.get(f"/v1/missions/{m['id']}").json()["autopilot"] is True
    r = client.post(f"/v1/missions/{m['id']}/requests/charlie/reply", json={"approve": True})
    assert r.status_code == 404
    assert r.json()["code"] == "request_not_found"


def test_errors(api: tuple[TestClient, Missions, Clock]) -> None:
    client, _, _ = api
    assert client.post("/v1/missions", json={"scenario_id": "nope", "player": "x"}).json()["code"] == (
        "scenario_not_found"
    )
    assert client.post("/v1/missions", json={"scenario_id": "contact_inconnu", "player": "x"}).json()[
        "code"
    ] == ("ship_not_found")
    assert client.get("/v1/missions/nope").json()["code"] == "mission_not_found"
    m = start(client)
    assert (
        client.post("/v1/missions", json={"scenario_id": "contact_inconnu", "player": "alfa"}).status_code
        == 409
    )
    r = client.post(f"/v1/missions/{m['id']}/contacts/TRK999/classification", json={"classification": "ami"})
    assert r.json()["code"] == "contact_not_found"
    assert client.post(f"/v1/missions/{m['id']}/orders", json={"text": ""}).status_code == 422
    assert client.delete(f"/v1/missions/{m['id']}").status_code == 204
    assert client.get(f"/v1/missions/{m['id']}").json()["phase"] == "ended"
    start(client)


def test_real_mode_without_sim_bridge() -> None:
    client, _, _ = app_client(adapters=AdapterMode.REAL)
    r = client.post("/v1/missions", json={"scenario_id": "contact_inconnu", "player": "hannibal"})
    assert r.status_code == 503
    assert r.json()["dependency"] == "sim-bridge"


def test_internal_token_required_when_configured() -> None:
    client, _, _ = app_client(internal_token="s3cret")
    assert client.get("/v1/scenarios").status_code == 401
    assert client.get("/v1/scenarios", headers={"X-Internal-Token": "s3cret"}).status_code == 200


def test_runner_loop_ticks_by_itself() -> None:
    settings = ApiSettings(adapters=AdapterMode.FAKE, log_json=True, mission_tick_s=0.01)  # type: ignore[call-arg]
    with TestClient(create_app(settings)) as client:
        m = start(client)
        for _ in range(200):
            if client.get(f"/v1/missions/{m['id']}").json()["ships"][0]["speed_mps"] > 0:
                break
            asyncio.run(asyncio.sleep(0.01))
        assert client.get(f"/v1/missions/{m['id']}").json()["ships"][0]["speed_mps"] > 0


def test_openapi_file_is_up_to_date() -> None:
    assert OPENAPI_FILE.read_text(encoding="utf-8") == render(), "relancer `uv run hx-export-openapi`"
