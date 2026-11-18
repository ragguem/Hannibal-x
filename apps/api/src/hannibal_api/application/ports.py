from collections.abc import Mapping
from typing import Any, Protocol

from hannibal_api.domain.readiness import ProbeResult


class DependencyProbe(Protocol):
    name: str
    required: bool

    async def check(self) -> ProbeResult: ...


class ScenarioCatalog(Protocol):
    """Scénarios validés par `hannibal_core.scenario.load`, indexés par identifiant."""

    def all(self) -> list[dict[str, Any]]: ...

    def get(self, scenario_id: str) -> dict[str, Any] | None: ...


class Clock(Protocol):
    def __call__(self) -> float: ...


class Simulator(Protocol):
    """Monde simulé (sim-bridge). Positions en mètres dans le repère local, points de route en lat/lon."""

    async def spawn(self, ships: Mapping[str, tuple[float, float, float]]) -> None: ...

    async def states(self) -> dict[str, dict[str, float]]: ...

    async def steer(self, waypoints: Mapping[str, tuple[float, float]]) -> None: ...

    async def clear(self) -> None: ...
