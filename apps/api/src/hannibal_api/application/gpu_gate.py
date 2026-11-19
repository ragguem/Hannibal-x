"""`GpuGate` (architecture 1.1.0 § 25) : admission des demandes qui occupent la carte partagée.

Deux classes : `voice` (transcription) et `doctrine` (question, explication). Une question ne démarre pas
tant qu'une transcription est active ou en attente ; une transcription n'attend jamais une question.
Pas de préemption : une rédaction en cours va au bout. Le jeton est rendu même sur annulation.
"""

import asyncio
import time
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass

from hannibal_api.application.missions import Busy


class DoctrineBusy(Busy):
    code = "doctrine_busy"
    message = "L'assistant de doctrine est occupé, réessayez dans un instant."


class SpeechBusy(Busy):
    code = "speech_busy"
    message = "La reconnaissance vocale est occupée, réessayez dans un instant."


@dataclass(frozen=True, slots=True)
class GateLimits:
    active: int
    waiting: int
    wait_s: float


@dataclass(frozen=True, slots=True)
class GateSnapshot:
    voice_active: int
    voice_waiting: int
    doctrine_active: int
    doctrine_waiting: int


class GpuGate:
    def __init__(self, *, voice: GateLimits, doctrine: GateLimits) -> None:
        self._voice = voice
        self._doctrine = doctrine
        self._on_wait: Callable[[str, float], None] | None = None
        self._changed = asyncio.Condition()
        self._voice_active = 0
        self._voice_waiting = 0
        self._doctrine_active = 0
        self._doctrine_waiting = 0

    def observe_waits(self, callback: Callable[[str, float], None]) -> None:
        self._on_wait = callback

    def snapshot(self) -> GateSnapshot:
        return GateSnapshot(
            self._voice_active, self._voice_waiting, self._doctrine_active, self._doctrine_waiting
        )

    def _voice_may_start(self) -> bool:
        return self._voice_active < self._voice.active

    def _doctrine_may_start(self) -> bool:
        return (
            self._doctrine_active < self._doctrine.active
            and self._voice_active == 0
            and self._voice_waiting == 0
        )

    @asynccontextmanager
    async def voice(self) -> AsyncIterator[None]:
        started = time.perf_counter()
        async with self._changed:
            if not self._voice_may_start() and self._voice_waiting >= self._voice.waiting:
                raise SpeechBusy(reason="queue_full")
            self._voice_waiting += 1
            try:
                await asyncio.wait_for(self._changed.wait_for(self._voice_may_start), self._voice.wait_s)
            except TimeoutError:
                raise SpeechBusy(reason="wait_timeout") from None
            finally:
                self._voice_waiting -= 1
                self._changed.notify_all()
            self._voice_active += 1
        self._report_wait("voice", started)
        try:
            yield
        finally:
            async with self._changed:
                self._voice_active -= 1
                self._changed.notify_all()

    @asynccontextmanager
    async def doctrine(self) -> AsyncIterator[None]:
        started = time.perf_counter()
        async with self._changed:
            if not self._doctrine_may_start() and self._doctrine_waiting >= self._doctrine.waiting:
                raise DoctrineBusy(reason="queue_full")
            self._doctrine_waiting += 1
            try:
                await asyncio.wait_for(
                    self._changed.wait_for(self._doctrine_may_start), self._doctrine.wait_s
                )
            except TimeoutError:
                raise DoctrineBusy(reason="wait_timeout") from None
            finally:
                self._doctrine_waiting -= 1
            self._doctrine_active += 1
        self._report_wait("doctrine", started)
        try:
            yield
        finally:
            async with self._changed:
                self._doctrine_active -= 1
                self._changed.notify_all()

    def _report_wait(self, kind: str, started: float) -> None:
        if self._on_wait is not None:
            self._on_wait(kind, time.perf_counter() - started)
