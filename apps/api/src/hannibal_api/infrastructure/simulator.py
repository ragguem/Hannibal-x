"""Simulateurs de remplacement de `sim-bridge`.

`InMemorySimulator` reprend la cinématique du banc de caractérisation (`run_fleet` de l'ancienne app) : chaque
navire tourne et accélère vers son point de route avec un taux borné.
"""

import math
import time
from collections.abc import Callable, Mapping

from hannibal_platform.errors import DependencyUnavailable

METERS_PER_DEGREE_LAT = 111320.0
MAX_TURN_RATE_DEG_PER_S = 4.0
MAX_ACCELERATION_MPS2 = 0.4
MIN_SPEED_MPS = 1.6
SPEED_PER_METER_TO_WAYPOINT = 0.414


class InMemorySimulator:
    def __init__(
        self, origin_lat_lon: tuple[float, float], clock: Callable[[], float] = time.monotonic
    ) -> None:
        self._origin_lat, self._origin_lon = origin_lat_lon
        self._clock = clock
        self._ships: dict[str, dict[str, float]] = {}
        self._last_step_at: float | None = None

    def _to_lat_lon(self, east_m: float, north_m: float) -> tuple[float, float]:
        lat = self._origin_lat + north_m / METERS_PER_DEGREE_LAT
        return lat, self._origin_lon + east_m / (METERS_PER_DEGREE_LAT * math.cos(math.radians(lat)))

    def _to_local(self, lat: float, lon: float) -> tuple[float, float]:
        east_m = (lon - self._origin_lon) * METERS_PER_DEGREE_LAT * math.cos(math.radians(lat))
        return east_m, (lat - self._origin_lat) * METERS_PER_DEGREE_LAT

    async def spawn(self, ships: Mapping[str, tuple[float, float, float]]) -> None:
        self._ships = {
            name: {"x": east_m, "y": north_m, "sog": 0.0, "hdg": heading_deg}
            for name, (east_m, north_m, heading_deg) in ships.items()
        }
        self._last_step_at = self._clock()

    async def states(self) -> dict[str, dict[str, float]]:
        states = {}
        for name, ship in self._ships.items():
            lat, lon = self._to_lat_lon(ship["x"], ship["y"])
            states[name] = {**ship, "lat": lat, "lon": lon}
        return states

    async def steer(self, waypoints: Mapping[str, tuple[float, float]]) -> None:
        now = self._clock()
        elapsed_s = 0.0 if self._last_step_at is None else now - self._last_step_at
        self._last_step_at = now
        max_turn_deg = MAX_TURN_RATE_DEG_PER_S * elapsed_s
        max_speed_change = MAX_ACCELERATION_MPS2 * elapsed_s
        for name, (waypoint_lat, waypoint_lon) in waypoints.items():
            ship = self._ships.get(name)
            if ship is None:
                continue
            waypoint_east, waypoint_north = self._to_local(waypoint_lat, waypoint_lon)
            distance_m = math.hypot(waypoint_east - ship["x"], waypoint_north - ship["y"])
            bearing_deg = (
                math.degrees(math.atan2(waypoint_east - ship["x"], waypoint_north - ship["y"])) % 360
            )
            turn_deg = ((bearing_deg - ship["hdg"] + 540.0) % 360.0) - 180.0
            ship["hdg"] = (ship["hdg"] + max(-max_turn_deg, min(max_turn_deg, turn_deg))) % 360
            target_speed = MIN_SPEED_MPS + SPEED_PER_METER_TO_WAYPOINT * distance_m
            ship["sog"] += max(-max_speed_change, min(max_speed_change, target_speed - ship["sog"]))
        for ship in self._ships.values():
            heading_rad = math.radians(ship["hdg"])
            ship["x"] += ship["sog"] * math.sin(heading_rad) * elapsed_s
            ship["y"] += ship["sog"] * math.cos(heading_rad) * elapsed_s

    async def clear(self) -> None:
        self._ships = {}
        self._last_step_at = None


class UnavailableSimulator:
    """Mode réel tant que `sim-bridge` n'existe pas : toute mission échoue en `dependency_unavailable`."""

    async def _fail(self) -> None:
        raise DependencyUnavailable("sim-bridge", "client sim-bridge pas encore livré")

    async def spawn(self, ships: Mapping[str, tuple[float, float, float]]) -> None:
        await self._fail()

    async def states(self) -> dict[str, dict[str, float]]:
        await self._fail()
        return {}

    async def steer(self, waypoints: Mapping[str, tuple[float, float]]) -> None:
        await self._fail()

    async def clear(self) -> None:
        await self._fail()
