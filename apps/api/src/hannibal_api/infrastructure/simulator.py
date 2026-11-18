"""Simulateur en mémoire : même cinématique que le banc de caractérisation (`run_fleet` de l'ancienne app)."""

import math
import time
from collections.abc import Callable, Mapping

from hannibal_platform.errors import DependencyUnavailable

M_PER_DEG = 111320.0
TURN_RATE = 4.0
ACCEL = 0.4


class FakeSimulator:
    def __init__(self, origin: tuple[float, float], clock: Callable[[], float] = time.monotonic) -> None:
        self._lat0, self._lon0 = origin
        self._clock = clock
        self._ships: dict[str, dict[str, float]] = {}
        self._last: float | None = None

    def _geo(self, x: float, y: float) -> tuple[float, float]:
        lat = self._lat0 + y / M_PER_DEG
        return lat, self._lon0 + x / (M_PER_DEG * math.cos(math.radians(lat)))

    def _local(self, lat: float, lon: float) -> tuple[float, float]:
        return (lon - self._lon0) * M_PER_DEG * math.cos(math.radians(lat)), (lat - self._lat0) * M_PER_DEG

    async def spawn(self, ships: Mapping[str, tuple[float, float, float]]) -> None:
        self._ships = {n: {"x": x, "y": y, "sog": 0.0, "hdg": hdg} for n, (x, y, hdg) in ships.items()}
        self._last = self._clock()

    async def states(self) -> dict[str, dict[str, float]]:
        out = {}
        for n, s in self._ships.items():
            lat, lon = self._geo(s["x"], s["y"])
            out[n] = {**s, "lat": lat, "lon": lon}
        return out

    async def steer(self, waypoints: Mapping[str, tuple[float, float]]) -> None:
        now = self._clock()
        dt = 0.0 if self._last is None else now - self._last
        self._last = now
        for n, (wlat, wlon) in waypoints.items():
            s = self._ships.get(n)
            if s is None:
                continue
            wx, wy = self._local(wlat, wlon)
            dist = math.hypot(wx - s["x"], wy - s["y"])
            brg = math.degrees(math.atan2(wx - s["x"], wy - s["y"])) % 360
            turn = ((brg - s["hdg"] + 540.0) % 360.0) - 180.0
            s["hdg"] = (s["hdg"] + max(-TURN_RATE * dt, min(TURN_RATE * dt, turn))) % 360
            target = 1.6 + 0.414 * dist
            s["sog"] += max(-ACCEL * dt, min(ACCEL * dt, target - s["sog"]))
        for s in self._ships.values():
            r = math.radians(s["hdg"])
            s["x"] += s["sog"] * math.sin(r) * dt
            s["y"] += s["sog"] * math.cos(r) * dt

    async def clear(self) -> None:
        self._ships = {}
        self._last = None


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
