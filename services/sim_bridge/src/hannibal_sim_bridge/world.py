"""Monde simulé vu par `sim-bridge`, dans le vocabulaire Hannibal : noms de navires, repère local, lat/lon."""

from collections.abc import Callable, Mapping
from typing import Protocol

from hannibal_core.fleet.vessel_model import KinematicFleet


class WorldUnavailable(Exception):
    """Le monde ne répond pas (LOTUSim arrêté, action refusée, délai) : l'appelant réessaie."""


class World(Protocol):
    async def start(self) -> None: ...

    async def stop(self) -> None: ...

    async def spawn(self, ships: Mapping[str, tuple[float, float, float]]) -> None:
        """Retire les navires présents puis crée ceux-ci : nom -> (est m, nord m, cap degrés)."""
        ...

    async def clear(self) -> None: ...

    async def states(self) -> dict[str, dict[str, float]]:
        """Nom -> x, y (m), lat, lon, sog (m/s), hdg (degrés vrais)."""
        ...

    async def steer(self, waypoints: Mapping[str, tuple[float, float]]) -> None: ...


class KinematicWorld:
    """Monde sans ROS pour le poste et les tests : la flotte avance à chaque pas de pilotage."""

    def __init__(self, origin_lat_lon: tuple[float, float], clock: Callable[[], float]) -> None:
        self._fleet = KinematicFleet(origin_lat_lon)
        self._clock = clock

    async def start(self) -> None:
        return None

    async def stop(self) -> None:
        return None

    async def spawn(self, ships: Mapping[str, tuple[float, float, float]]) -> None:
        self._fleet.spawn(ships, self._clock())

    async def clear(self) -> None:
        self._fleet.clear()

    async def states(self) -> dict[str, dict[str, float]]:
        return self._fleet.states()

    async def steer(self, waypoints: Mapping[str, tuple[float, float]]) -> None:
        self._fleet.steer(waypoints, self._clock())
