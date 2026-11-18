"""Le client `sim-bridge` de l'API contre le vrai service (monde cinématique), sans réseau."""

import httpx
import pytest

from hannibal_api.application.ports import FleetUnavailable, ManeuverRejected
from hannibal_api.infrastructure.sim_bridge import SimBridgeClient
from hannibal_platform.errors import DependencyUnavailable
from hannibal_sim_bridge.main import create_app
from hannibal_sim_bridge.registry import ManeuverRegistry
from hannibal_sim_bridge.settings import SimBridgeSettings, WorldKind
from hannibal_sim_bridge.world import KinematicWorld

TOKEN = "jeton-interne-de-test"


class ManualClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def bridge_client(clock: ManualClock) -> SimBridgeClient:
    settings = SimBridgeSettings(  # type: ignore[call-arg]
        world=WorldKind.KINEMATIC, internal_token=TOKEN, log_json=True
    )
    app = create_app(settings, world=KinematicWorld((43.0, 6.0), clock), registry=ManeuverRegistry())
    return SimBridgeClient(
        "http://sim-bridge", token=TOKEN, timeout_s=2.0, transport=httpx.ASGITransport(app=app)
    )


async def test_simulator_calls_drive_the_bridge_world() -> None:
    clock = ManualClock()
    client = bridge_client(clock)
    await client.spawn({"hannibal": (0.0, 0.0, 90.0), "alfa": (-400.0, 0.0, 90.0)})
    for _ in range(10):
        clock.now += 0.5
        await client.steer({"hannibal": (43.0, 6.01)})

    states = await client.states()
    assert set(states) == {"hannibal", "alfa"}
    assert states["hannibal"]["x"] > 0
    assert states["alfa"]["sog"] == 0

    await client.clear()
    assert await client.states() == {}
    await client.aclose()


async def test_dispatch_is_idempotent_and_known_after_success() -> None:
    client = bridge_client(ManualClock())
    maneuver = {"to": "alfa", "orders": [{"op": "speed", "kn": 12}]}
    assert not await client.knows("cmd-1")

    await client.dispatch("cmd-1", maneuver)
    await client.dispatch("cmd-1", maneuver)
    assert await client.knows("cmd-1")

    with pytest.raises(ManeuverRejected):
        await client.dispatch("cmd-1", {"to": "delta"})
    await client.aclose()


async def test_unreachable_bridge_is_transient() -> None:
    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    client = SimBridgeClient(
        "http://sim-bridge", token=None, timeout_s=1.0, transport=httpx.MockTransport(refuse)
    )
    with pytest.raises(FleetUnavailable):
        await client.dispatch("cmd-1", {"to": "alfa"})
    with pytest.raises(FleetUnavailable):
        await client.knows("cmd-1")
    with pytest.raises(DependencyUnavailable):
        await client.states()


async def test_unconfigured_bridge_fails_without_network() -> None:
    client = SimBridgeClient("", token=None, timeout_s=1.0)
    with pytest.raises(FleetUnavailable):
        await client.dispatch("cmd-1", {"to": "alfa"})
    with pytest.raises(DependencyUnavailable):
        await client.spawn({"alfa": (0.0, 0.0, 0.0)})
