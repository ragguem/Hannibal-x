from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum


class ProbeState(StrEnum):
    UP = "up"
    DOWN = "down"
    DISABLED = "disabled"


@dataclass(frozen=True, slots=True)
class ProbeResult:
    name: str
    state: ProbeState
    required: bool
    latency_ms: float | None = None
    reason: str | None = None


class OverallState(StrEnum):
    READY = "ready"
    DEGRADED = "degraded"


def overall_state(results: Iterable[ProbeResult]) -> OverallState:
    """Prêt si aucune dépendance requise n'est en panne ; une dépendance optionnelle ne bloque pas."""
    if any(r.required and r.state is not ProbeState.UP for r in results):
        return OverallState.DEGRADED
    return OverallState.READY
