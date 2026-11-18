from collections.abc import Mapping
from typing import Any, Protocol

from hannibal_api.domain.audit import AuditEntry, AuditRecord, ChainVerification, MissionOutcome
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


class MissionJournal(Protocol):
    """Écrit, dans une seule transaction, l'état persistant de la mission, l'audit et le fait métier."""

    async def mission_started(
        self, mission_id: str, scenario_id: str, player_ship: str, owner_id: str, entry: AuditEntry
    ) -> None: ...

    async def mission_finished(
        self, mission_id: str, outcome: MissionOutcome, debrief: dict[str, Any] | None, entry: AuditEntry
    ) -> None: ...

    async def record(self, entry: AuditEntry) -> None: ...

    async def interrupt_unfinished(self) -> list[str]:
        """Au démarrage : les missions restées `running` ont perdu leur moteur en mémoire."""
        ...


class AuditReader(Protocol):
    async def read(self, mission_id: str | None, after_seq: int, limit: int) -> list[AuditRecord]: ...

    async def verify(self) -> ChainVerification: ...
