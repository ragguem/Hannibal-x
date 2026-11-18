import math
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from hannibal_sim_bridge.main import create_app
from hannibal_sim_bridge.registry import ManeuverRegistry
from hannibal_sim_bridge.ros import heading_from_quaternion, quaternion_z_w_from_heading, ship_state
from hannibal_sim_bridge.settings import SimBridgeSettings, WorldKind
from hannibal_sim_bridge.world import KinematicWorld, WorldUnavailable

TOKEN = "jeton-interne-de-test"


class ManualClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def make_client(tmp_path: Path, *, clock: ManualClock | None = None, token: str | None = None) -> TestClient:
    settings = SimBridgeSettings(  # type: ignore[call-arg]
        world=WorldKind.KINEMATIC, internal_token=token, log_json=True
    )
    world = KinematicWorld(settings.origin_lat_lon, clock or ManualClock())
    registry = ManeuverRegistry(tmp_path / "maneuvers.jsonl")
    return TestClient(create_app(settings, world=world, registry=registry))


def test_spawn_steer_and_read_state(tmp_path: Path) -> None:
    clock = ManualClock()
    client = make_client(tmp_path, clock=clock)
    spawned = client.post(
        "/ships",
        json={"ships": [{"name": "alfa", "east_m": 0, "north_m": 0, "heading_deg": 0}]},
    )
    assert spawned.status_code == 204

    north_lat = 43.0 + 500 / 111320.0
    for _ in range(20):
        clock.now += 0.5
        steered = client.put("/waypoints", json={"waypoints": {"alfa": {"lat": north_lat, "lon": 6.0}}})
        assert steered.status_code == 204

    ship = client.get("/state").json()["ships"]["alfa"]
    assert ship["y"] > 10
    assert ship["sog"] > 0
    assert abs(ship["x"]) < 1e-6

    assert client.delete("/ships").status_code == 204
    assert client.get("/state").json() == {"ships": {}}


def test_maneuvers_are_recorded_once_and_survive_a_restart(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    body = {"command_id": "cmd-1", "maneuver": {"to": "alfa", "orders": [{"op": "speed", "kn": 12}]}}

    first = client.post("/maneuvers", json=body)
    again = client.post("/maneuvers", json=body)
    assert (first.status_code, again.status_code) == (201, 200)
    assert again.json()["recorded_at"] == first.json()["recorded_at"]

    conflicting = client.post("/maneuvers", json={**body, "maneuver": {"to": "delta"}})
    assert conflicting.status_code == 409

    restarted = make_client(tmp_path)
    assert restarted.get("/maneuvers/cmd-1").json()["maneuver"] == body["maneuver"]
    assert restarted.get("/maneuvers/unknown").status_code == 404


def test_internal_token_is_required_when_configured(tmp_path: Path) -> None:
    client = make_client(tmp_path, token=TOKEN)
    assert client.get("/state").status_code == 401
    assert client.get("/state", headers={"X-Internal-Token": "faux"}).status_code == 403
    assert client.get("/state", headers={"X-Internal-Token": TOKEN}).status_code == 200
    assert client.get("/health").status_code == 200


def test_world_failure_is_reported_as_dependency_unavailable(tmp_path: Path) -> None:
    class BrokenWorld(KinematicWorld):
        async def states(self) -> dict[str, dict[str, float]]:
            raise WorldUnavailable("LOTUSim arrêté")

    settings = SimBridgeSettings(world=WorldKind.KINEMATIC, log_json=True)  # type: ignore[call-arg]
    app = create_app(settings, world=BrokenWorld((43.0, 6.0), ManualClock()), registry=ManeuverRegistry())
    response = TestClient(app).get("/state")
    assert response.status_code == 503
    assert response.json()["dependency"] == "lotusim"


@pytest.mark.parametrize("heading", [0.0, 45.0, 90.0, 180.0, 271.5])
def test_heading_round_trips_through_lotusim_orientation(heading: float) -> None:
    z, w = quaternion_z_w_from_heading(heading)
    assert heading_from_quaternion(0.0, 0.0, z, w) == pytest.approx(heading % 360, abs=1e-9)


def test_vessel_position_is_translated_to_hannibal_state() -> None:
    z, w = quaternion_z_w_from_heading(90.0)
    vessel = SimpleNamespace(
        pose=SimpleNamespace(
            position=SimpleNamespace(x=120.0, y=-40.0), orientation=SimpleNamespace(x=0.0, y=0.0, z=z, w=w)
        ),
        geo_point=SimpleNamespace(latitude=43.1, longitude=6.2),
        speed_over_ground=7.5,
    )
    state = ship_state(vessel)
    assert state == {"x": 120.0, "y": -40.0, "lat": 43.1, "lon": 6.2, "sog": 7.5, "hdg": pytest.approx(90.0)}
    assert not math.isnan(state["hdg"])
