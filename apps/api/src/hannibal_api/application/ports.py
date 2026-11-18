from typing import Protocol

from hannibal_api.domain.readiness import ProbeResult


class DependencyProbe(Protocol):
    name: str
    required: bool

    async def check(self) -> ProbeResult: ...
