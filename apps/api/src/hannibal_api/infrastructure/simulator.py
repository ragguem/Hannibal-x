"""Simulateur du mode `fake` : le monde cinématique de `hannibal_core`, sans `sim-bridge`."""

import time
from collections.abc import Callable, Mapping

from hannibal_core.fleet.vessel_model import KinematicFleet


class InMemorySimulator:
    def __init__(
        self, origin_lat_lon: tuple[float, float], clock: Callable[[], float] = time.monotonic
    ) -> None:
        self._fleet = KinematicFleet(origin_lat_lon)
        self._clock = clock

    async def spawn(self, ships: Mapping[str, tuple[float, float, float]]) -> None:
        self._fleet.spawn(ships, self._clock())

    async def states(self) -> dict[str, dict[str, float]]:
        return self._fleet.states()

    async def steer(self, waypoints: Mapping[str, tuple[float, float]]) -> None:
        self._fleet.steer(waypoints, self._clock())

    async def clear(self) -> None:
        self._fleet.clear()
