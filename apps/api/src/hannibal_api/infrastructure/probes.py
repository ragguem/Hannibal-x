import time

import asyncpg
import httpx

from hannibal_api.domain.readiness import ProbeResult, ProbeState
from hannibal_platform.logging import get_logger

log = get_logger(__name__)


def _elapsed_ms(started: float) -> float:
    return round((time.perf_counter() - started) * 1000, 1)


class PostgresProbe:
    name = "postgres"
    required = True

    def __init__(self, dsn: str | None, timeout_s: float) -> None:
        self._dsn = dsn
        self._timeout_s = timeout_s

    async def check(self) -> ProbeResult:
        if not self._dsn:
            return ProbeResult(self.name, ProbeState.DOWN, self.required, reason="not_configured")
        started = time.perf_counter()
        try:
            connection = await asyncpg.connect(self._dsn, timeout=self._timeout_s)
            try:
                await connection.fetchval("SELECT 1")
            finally:
                await connection.close()
        except (OSError, TimeoutError, asyncpg.PostgresError) as exc:
            log.warning("probe_down", dependency=self.name, error_type=type(exc).__name__)
            return ProbeResult(self.name, ProbeState.DOWN, self.required, reason=type(exc).__name__)
        return ProbeResult(self.name, ProbeState.UP, self.required, latency_ms=_elapsed_ms(started))


class HttpProbe:
    """Sonde HTTP simple (GET, réponse 200 attendue) pour un service optionnel comme Ollama."""

    def __init__(self, name: str, url: str | None, timeout_s: float, *, required: bool = False) -> None:
        self.name = name
        self.required = required
        self._url = url
        self._timeout_s = timeout_s

    async def check(self) -> ProbeResult:
        if not self._url:
            return ProbeResult(self.name, ProbeState.DISABLED, self.required, reason="not_configured")
        started = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=self._timeout_s) as client:
                response = await client.get(self._url)
        except httpx.HTTPError as exc:
            log.warning("probe_down", dependency=self.name, error_type=type(exc).__name__)
            return ProbeResult(self.name, ProbeState.DOWN, self.required, reason=type(exc).__name__)
        if response.status_code != 200:
            return ProbeResult(
                self.name, ProbeState.DOWN, self.required, reason=f"http_{response.status_code}"
            )
        return ProbeResult(self.name, ProbeState.UP, self.required, latency_ms=_elapsed_ms(started))


class FakeProbe:
    """Sonde factice pour le mode `fake` (poste de développement sans base ni GPU) et les tests."""

    def __init__(self, name: str, state: ProbeState = ProbeState.UP, *, required: bool = True) -> None:
        self.name = name
        self.required = required
        self._state = state

    async def check(self) -> ProbeResult:
        return ProbeResult(self.name, self._state, self.required, latency_ms=0.0)
