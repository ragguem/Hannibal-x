import asyncio
from collections.abc import Sequence
from dataclasses import dataclass

from hannibal_api.application.ports import DependencyProbe
from hannibal_api.domain.readiness import OverallState, ProbeResult, ProbeState, overall_state


@dataclass(frozen=True, slots=True)
class ReadinessReport:
    state: OverallState
    dependencies: tuple[ProbeResult, ...]


class CheckReadiness:
    """Interroge toutes les sondes en parallèle ; une sonde trop lente compte comme en panne."""

    def __init__(self, probes: Sequence[DependencyProbe], timeout_s: float) -> None:
        self._probes = tuple(probes)
        self._timeout_s = timeout_s

    async def _run(self, probe: DependencyProbe) -> ProbeResult:
        try:
            return await asyncio.wait_for(probe.check(), self._timeout_s)
        except TimeoutError:
            return ProbeResult(probe.name, ProbeState.DOWN, probe.required, reason="timeout")

    async def __call__(self) -> ReadinessReport:
        results = await asyncio.gather(*(self._run(p) for p in self._probes))
        return ReadinessReport(overall_state(results), tuple(results))
