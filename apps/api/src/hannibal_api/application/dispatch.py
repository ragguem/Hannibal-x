"""Répartiteur des manœuvres approuvées (§ 7, envoi fiable).

Un envoi à la fois, dans l'ordre des décisions, pour qu'un ordre récent ne passe pas devant un plus ancien.
Une manœuvre n'est jamais marquée partie sans l'être, ni exécutée deux fois, ni exécutée après son échéance.
"""

import asyncio
import contextlib

from hannibal_api.application.missions import Missions
from hannibal_api.application.ports import CommandStore, FleetPort, FleetUnavailable, ManeuverRejected
from hannibal_api.domain.audit import AuditEntry, AuditEvent
from hannibal_api.domain.commands import Dispatch, DispatchFailure, retry_delay_s
from hannibal_platform.logging import get_logger

log = get_logger(__name__)


class Dispatcher:
    def __init__(
        self,
        store: CommandStore,
        fleet: FleetPort,
        missions: Missions,
        *,
        max_attempts: int,
        attempt_timeout_s: float,
        poll_period_s: float,
    ) -> None:
        self._store = store
        self._fleet = fleet
        self._missions = missions
        self._max_attempts = max_attempts
        self._attempt_timeout_s = attempt_timeout_s
        self._poll_period_s = poll_period_s
        self._wake = asyncio.Event()
        self._task: asyncio.Task[None] | None = None

    def wake(self) -> None:
        self._wake.set()

    def start(self) -> None:
        if self._poll_period_s > 0:
            self._task = asyncio.create_task(self._run_forever(), name="dispatcher")

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task

    async def reconcile(self) -> None:
        """Au démarrage : une ligne restée `in_flight` a peut-être été envoyée avant l'arrêt de l'API.

        Simulateur injoignable : la ligne reste `in_flight`, le répartiteur ne la reprend pas à l'aveugle.
        """
        for dispatch in await self._store.in_flight():
            try:
                executed = await self._fleet.knows(dispatch.command_id)
            except FleetUnavailable as error:
                log.warning("dispatch_not_reconciled", command_id=dispatch.command_id, error=str(error))
                continue
            if executed:
                await self._store.mark_dispatched(
                    dispatch.command_id,
                    self._entry(AuditEvent.SIMULATOR_DISPATCHED, dispatch, {"reconciled": True}),
                )
            else:
                await self._store.requeue(dispatch.command_id)

    async def dispatch_next(self) -> bool:
        """Traite une ligne ; `False` s'il n'y avait rien à envoyer."""
        dispatch = await self._store.claim_next()
        if dispatch is None:
            return False
        if dispatch.expired:
            await self._fail(dispatch, DispatchFailure.DEADLINE_PASSED)
        elif not self._missions.is_active(dispatch.mission_id):
            await self._fail(dispatch, DispatchFailure.MISSION_ENDED)
        elif not self._missions.check_order(dispatch.mission_id, dispatch.text)["ok"]:
            await self._fail(dispatch, DispatchFailure.ORDER_NO_LONGER_VALID)
        else:
            await self._send(dispatch)
        return True

    async def _send(self, dispatch: Dispatch) -> None:
        try:
            async with asyncio.timeout(self._attempt_timeout_s):
                await self._fleet.dispatch(dispatch.command_id, dispatch.maneuver)
        except ManeuverRejected as error:
            await self._fail(dispatch, DispatchFailure.MANEUVER_REJECTED, detail=str(error))
        except (FleetUnavailable, TimeoutError) as error:
            detail = str(error) or type(error).__name__
            if dispatch.attempts >= self._max_attempts:
                await self._fail(dispatch, DispatchFailure.ATTEMPTS_EXHAUSTED, detail=detail)
                return
            delay_s = retry_delay_s(dispatch.attempts)
            await self._store.retry_later(
                dispatch.command_id,
                delay_s,
                detail,
                self._entry(
                    AuditEvent.DISPATCH_RETRY, dispatch, {"attempts": dispatch.attempts, "error": detail}
                ),
            )
            log.warning(
                "dispatch_retry", command_id=dispatch.command_id, attempts=dispatch.attempts, error=detail
            )
        else:
            self._missions.apply_dispatched_order(dispatch.mission_id, dispatch.text)
            await self._store.mark_dispatched(
                dispatch.command_id,
                self._entry(AuditEvent.SIMULATOR_DISPATCHED, dispatch, {"attempts": dispatch.attempts}),
            )
            log.info("command_dispatched", command_id=dispatch.command_id, attempts=dispatch.attempts)

    async def _fail(self, dispatch: Dispatch, failure: DispatchFailure, detail: str | None = None) -> None:
        error = failure.value if detail is None else f"{failure.value}: {detail}"
        await self._store.mark_failed(
            dispatch.command_id,
            error,
            self._entry(AuditEvent.DISPATCH_FAILED, dispatch, {"reason": failure.value, "detail": detail}),
        )
        log.warning("dispatch_failed", command_id=dispatch.command_id, reason=failure.value, detail=detail)

    @staticmethod
    def _entry(event: AuditEvent, dispatch: Dispatch, payload: dict[str, object]) -> AuditEntry:
        return AuditEntry(event, None, dispatch.mission_id, dict(payload), command_id=dispatch.command_id)

    async def _run_forever(self) -> None:
        while True:
            try:
                if await self.dispatch_next():
                    continue
            except Exception:
                log.exception("dispatcher_step_failed")
            self._wake.clear()
            with contextlib.suppress(TimeoutError):
                async with asyncio.timeout(self._poll_period_s):
                    await self._wake.wait()
