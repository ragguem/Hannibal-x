"""Client `sim-bridge` du mode `real` : monde simulé (`Simulator`) et registre des manœuvres (`FleetPort`)."""

from collections.abc import Mapping
from typing import Any

import httpx
from pydantic import BaseModel

from hannibal_api.application.ports import FleetUnavailable, ManeuverRejected
from hannibal_contracts import sim_bridge as contract
from hannibal_platform.errors import DependencyUnavailable
from hannibal_platform.internal_client import InternalClient

DEPENDENCY = "sim-bridge"


class SimBridgeClient:
    def __init__(
        self,
        base_url: str,
        *,
        token: str | None,
        timeout_s: float,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._client = InternalClient(
            DEPENDENCY, base_url, token=token, timeout_s=timeout_s, transport=transport
        )

    async def _send(self, method: str, path: str, body: BaseModel | None = None) -> httpx.Response:
        payload = body.model_dump(mode="json") if body is not None else None
        response = await self._client.request(method, path, json=payload)
        if response.status_code >= 400 and response.status_code not in (404, 409, 422):
            raise DependencyUnavailable(DEPENDENCY, f"réponse {response.status_code}")
        return response

    async def spawn(self, ships: Mapping[str, tuple[float, float, float]]) -> None:
        placements = [
            contract.ShipPlacement(name=name, east_m=east_m, north_m=north_m, heading_deg=heading_deg % 360)
            for name, (east_m, north_m, heading_deg) in ships.items()
        ]
        self._expect_success(await self._send("POST", "/ships", contract.SpawnFleet(ships=placements)))

    async def states(self) -> dict[str, dict[str, float]]:
        response = await self._send("GET", "/state")
        self._expect_success(response)
        world = contract.WorldState.model_validate_json(response.content)
        return {name: ship.model_dump() for name, ship in world.ships.items()}

    async def steer(self, waypoints: Mapping[str, tuple[float, float]]) -> None:
        body = contract.SteerFleet(
            waypoints={name: contract.GeoWaypoint(lat=lat, lon=lon) for name, (lat, lon) in waypoints.items()}
        )
        self._expect_success(await self._send("PUT", "/waypoints", body))

    async def clear(self) -> None:
        self._expect_success(await self._send("DELETE", "/ships"))

    async def dispatch(self, command_id: str, maneuver: Mapping[str, Any]) -> None:
        body = contract.RecordManeuver(command_id=command_id, maneuver=dict(maneuver))
        try:
            response = await self._send("POST", "/maneuvers", body)
        except DependencyUnavailable as error:
            raise FleetUnavailable(error.detail or DEPENDENCY) from error
        if response.status_code in (409, 422):
            raise ManeuverRejected(f"sim-bridge a refusé la manœuvre ({response.status_code})")
        self._expect_success(response)

    async def knows(self, command_id: str) -> bool:
        try:
            response = await self._send("GET", f"/maneuvers/{command_id}")
        except DependencyUnavailable as error:
            raise FleetUnavailable(error.detail or DEPENDENCY) from error
        return response.status_code == 200

    async def aclose(self) -> None:
        await self._client.aclose()

    @staticmethod
    def _expect_success(response: httpx.Response) -> None:
        if response.status_code >= 400:
            raise DependencyUnavailable(DEPENDENCY, f"réponse {response.status_code}")
