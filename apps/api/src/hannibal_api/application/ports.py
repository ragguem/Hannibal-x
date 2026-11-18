from collections.abc import Mapping
from typing import Any, Protocol

from hannibal_api.domain.audit import AuditEntry, AuditRecord, ChainVerification, MissionOutcome
from hannibal_api.domain.commands import Command, CommandDecision, CommandState, Dispatch
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


class FleetUnavailable(Exception):
    """Échec transitoire de l'envoi (délai, `503`, LOTUSim déconnecté) : le répartiteur réessaie."""


class ManeuverRejected(Exception):
    """Refus définitif du simulateur : la manœuvre n'est pas renvoyée."""


class FleetPort(Protocol):
    """Envoi des manœuvres approuvées. Idempotent : un identifiant déjà exécuté n'est pas rejoué."""

    async def dispatch(self, command_id: str, maneuver: Mapping[str, Any]) -> None: ...

    async def knows(self, command_id: str) -> bool:
        """Réconciliation au démarrage : la manœuvre a-t-elle été exécutée ?"""
        ...


class CommandStore(Protocol):
    """Commandes et registre des envois. Chaque écriture se fait avec son audit, dans une transaction."""

    async def create(self, command: Command, entry: AuditEntry) -> None: ...

    async def get(self, command_id: str) -> Command | None: ...

    async def decide(
        self,
        command_id: str,
        expected: CommandState,
        decision: CommandDecision,
        actor_id: str,
        validity_s: float,
        entry: AuditEntry,
    ) -> Command | None:
        """Applique la décision si la commande est encore dans l'état attendu ; `None` sinon.

        `approve` et `retry` inscrivent l'envoi (`queued`, échéance = maintenant + validité pour `approve`).
        """
        ...

    async def claim_next(self) -> Dispatch | None:
        """Prend la plus ancienne ligne `queued` arrivée à échéance de tentative et la passe `in_flight`."""
        ...

    async def mark_dispatched(self, command_id: str, entry: AuditEntry) -> None: ...

    async def retry_later(self, command_id: str, delay_s: float, error: str, entry: AuditEntry) -> None: ...

    async def mark_failed(self, command_id: str, error: str, entry: AuditEntry) -> None: ...

    async def in_flight(self) -> list[Dispatch]: ...

    async def requeue(self, command_id: str) -> None: ...


class AuditReader(Protocol):
    async def read(self, mission_id: str | None, after_seq: int, limit: int) -> list[AuditRecord]: ...

    async def verify(self) -> ChainVerification: ...
