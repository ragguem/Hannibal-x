"""Adaptateurs de `FleetPort` en attendant le client `sim-bridge` (`POST /maneuvers`)."""

from collections.abc import Mapping
from typing import Any

from hannibal_api.application.ports import FleetUnavailable, ManeuverRejected


class InMemoryFleet:
    """Mode `fake` : accepte chaque manœuvre une seule fois. Les pannes se programment pour les tests."""

    def __init__(self) -> None:
        self.maneuver_by_command: dict[str, dict[str, Any]] = {}
        self.dispatch_calls = 0
        self.failures_before_success = 0
        self.rejection_reason: str | None = None

    async def dispatch(self, command_id: str, maneuver: Mapping[str, Any]) -> None:
        self.dispatch_calls += 1
        if self.rejection_reason is not None:
            raise ManeuverRejected(self.rejection_reason)
        if self.failures_before_success > 0:
            self.failures_before_success -= 1
            raise FleetUnavailable("sim-bridge injoignable")
        self.maneuver_by_command.setdefault(command_id, dict(maneuver))

    async def knows(self, command_id: str) -> bool:
        return command_id in self.maneuver_by_command


class UnavailableFleet:
    """Mode `real` tant que le client `sim-bridge` n'est pas livré : chaque envoi échoue en transitoire."""

    async def dispatch(self, command_id: str, maneuver: Mapping[str, Any]) -> None:
        raise FleetUnavailable("client sim-bridge non livré")

    async def knows(self, command_id: str) -> bool:
        raise FleetUnavailable("client sim-bridge non livré")
