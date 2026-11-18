"""Handlers de mission (§ 12) autour du moteur `hannibal_core.scenario`.

Une seule mission tourne à la fois : le simulateur n'a qu'un monde. Le registre métier
(`ops.audit_events`) et le flux SSE arrivent avec le schéma `ops`.
"""

import asyncio
import random
import uuid
from dataclasses import dataclass, field
from typing import Any, ClassVar

from hannibal_core.scenario import ScenarioEngine

from hannibal_api.application.ports import Clock, ScenarioCatalog, Simulator
from hannibal_platform.logging import get_logger

log = get_logger(__name__)


class MissionError(Exception):
    """Refus métier ; la présentation le traduit en `{ code, message, request_id }`."""

    code: ClassVar[str]
    message: ClassVar[str]

    def __init__(self, **context: object) -> None:
        super().__init__(self.message)
        self.context = context


class NotFound(MissionError):
    pass


class Conflict(MissionError):
    pass


class ScenarioNotFound(NotFound):
    code = "scenario_not_found"
    message = "Scénario inconnu."


class MissionNotFound(NotFound):
    code = "mission_not_found"
    message = "Mission inconnue."


class UnknownShip(NotFound):
    code = "ship_not_found"
    message = "Ce navire ne fait pas partie du scénario."


class ContactNotFound(NotFound):
    code = "contact_not_found"
    message = "Piste inconnue."


class NoPendingRequest(NotFound):
    code = "request_not_found"
    message = "Aucune demande en attente pour ce navire."


class MissionAlreadyRunning(Conflict):
    code = "mission_running"
    message = "Une mission est déjà en cours."


class MissionEnded(Conflict):
    code = "mission_ended"
    message = "La mission est terminée."


class ManualHelmInactive(Conflict):
    code = "manual_helm_inactive"
    message = "La barre manuelle n'est pas active."


@dataclass(slots=True)
class MissionRun:
    id: str
    scenario_id: str
    operator: str
    engine: ScenarioEngine
    stopped: bool = False
    task: asyncio.Task[None] | None = field(default=None, repr=False)

    @property
    def ended(self) -> bool:
        return bool(self.engine.run["ended"])


class Missions:
    def __init__(self, catalog: ScenarioCatalog, simulator: Simulator, clock: Clock, tick_s: float) -> None:
        self._catalog = catalog
        self._sim = simulator
        self._clock = clock
        self._tick_s = tick_s
        self._runs: dict[str, MissionRun] = {}

    def list_scenarios(self) -> list[dict[str, Any]]:
        return self._catalog.all()

    async def start(
        self, scenario_id: str, player: str, *, operator: str, autopilot: bool, manual: bool
    ) -> MissionRun:
        sc = self._catalog.get(scenario_id)
        if sc is None:
            raise ScenarioNotFound(scenario_id=scenario_id)
        if player not in {f["nom"] for f in sc["flotte"]}:
            raise UnknownShip(ship=player)
        if any(not r.stopped and not r.ended for r in self._runs.values()):
            raise MissionAlreadyRunning
        cap = float(sc.get("cap_initial", 0))
        await self._sim.clear()
        await self._sim.spawn({n: (x, y, cap) for n, (x, y) in ScenarioEngine.initial_positions(sc).items()})
        engine = ScenarioEngine(
            sc,
            player,
            clock=self._clock,
            rng=random.Random(),  # noqa: S311 — tirage d'exercice, pas de la cryptographie
            auto=autopilot,
            manual=manual,
        )
        engine.st = await self._sim.states()
        run = MissionRun(str(uuid.uuid4()), scenario_id, operator, engine)
        self._runs[run.id] = run
        if self._tick_s > 0:
            run.task = asyncio.create_task(self._loop(run), name=f"mission-{run.id}")
        log.info(
            "mission_started", mission_id=run.id, scenario_id=scenario_id, player=player, operator=operator
        )
        return run

    async def step(self, mission_id: str) -> None:
        """Un pas du `MissionRunner` : état du monde, moteur, points de route."""
        run = self.read(mission_id)
        if run.stopped or run.ended:
            return
        waypoints = run.engine.tick(await self._sim.states())
        if waypoints:
            await self._sim.steer(waypoints)
        if run.ended:
            log.info("mission_finished", mission_id=run.id, debrief=run.engine.run["debrief"])

    async def _loop(self, run: MissionRun) -> None:
        while not run.stopped and not run.ended:
            try:
                await self.step(run.id)
            except Exception:
                log.exception("mission_tick_failed", mission_id=run.id)
            await asyncio.sleep(self._tick_s)

    def read(self, mission_id: str) -> MissionRun:
        run = self._runs.get(mission_id)
        if run is None:
            raise MissionNotFound(mission_id=mission_id)
        return run

    def _live(self, mission_id: str) -> MissionRun:
        run = self.read(mission_id)
        if run.stopped or run.ended:
            raise MissionEnded(mission_id=mission_id)
        return run

    async def stop(self, mission_id: str) -> None:
        run = self.read(mission_id)
        run.stopped = True
        if run.task is not None:
            run.task.cancel()
        await self._sim.clear()
        log.info("mission_stopped", mission_id=mission_id)

    async def shutdown(self) -> None:
        for run in self._runs.values():
            run.stopped = True
            if run.task is not None:
                run.task.cancel()

    def submit_order(self, mission_id: str, text: str) -> dict[str, Any]:
        return dict(self._live(mission_id).engine.player_order(text))

    def simulate(self, mission_id: str, text: str) -> dict[str, Any]:
        return dict(self.read(mission_id).engine.simulate(text))

    def recommend(self, mission_id: str) -> list[dict[str, str]]:
        return list(self.read(mission_id).engine.recommend())

    def set_helm(self, mission_id: str, change: dict[str, float]) -> dict[str, Any]:
        result = self._live(mission_id).engine.helm(change)
        if not result["ok"]:
            raise ManualHelmInactive
        return dict(result["helm"])

    def classify(self, mission_id: str, contact_id: str, classification: str) -> None:
        if not self.read(mission_id).engine.classify(contact_id, classification):
            raise ContactNotFound(contact_id=contact_id)

    def reply(self, mission_id: str, ship: str, approve: bool) -> str:
        result = self._live(mission_id).engine.reply(ship, approve)
        if not result["ok"]:
            raise NoPendingRequest(ship=ship)
        return str(result["en"])

    def set_autopilot(self, mission_id: str, enabled: bool) -> None:
        self._live(mission_id).engine.set_auto(enabled)
