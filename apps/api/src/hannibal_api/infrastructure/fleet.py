"""Faux `FleetPort` du mode `fake` ; le mode `real` passe par `SimBridgeClient`."""

from collections.abc import Mapping
from typing import Any

from hannibal_api.application.ports import FleetUnavailable, ManeuverRejected


class InMemoryFleet:
    """Accepte chaque manœuvre une seule fois. Les pannes se programment pour les tests."""

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
