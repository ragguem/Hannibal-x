"""Handlers de mission (§ 12) autour du moteur `hannibal_core.scenario`.

Une seule mission tourne à la fois : le simulateur n'a qu'un monde. Le registre métier
(`ops.audit_events`) et le flux SSE arrivent avec le schéma `ops`.
"""

import asyncio
import random
from dataclasses import dataclass, field
from typing import Any, ClassVar

from hannibal_core.orders.limits import SpeedLimits
from hannibal_core.scenario import ScenarioEngine, ScenarioError, load
from hannibal_core.signals import KB

from hannibal_api.application.ports import Clock, MissionJournal, Simulator
from hannibal_api.domain.audit import AuditEntry, AuditEvent, FactType, MissionOutcome
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


class Unprocessable(MissionError):
    pass


class Forbidden(MissionError):
    pass


class Busy(MissionError):
    pass


class InvalidScenario(Unprocessable):
    code = "scenario_invalid"
    message = "Le document du scénario n'est pas conforme."


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


def reading_summary(reading: dict[str, Any]) -> dict[str, Any]:
    """Ce que le registre garde de la lecture : méthode, signal et référence dans la publication, notes."""
    return {
        "method": str(reading["method"]),
        "signal": reading["signal"],
        "reference": reading["reference"],
        "notes": reading["notes"],
    }


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

    @property
    def active(self) -> bool:
        return not self.stopped and not self.ended


class Missions:
    """Handlers `RunMission`, `ReadMission`, `StopMission`, `SubmitOrder`, `SimulateOrder`,
    `Recommend`, `SetHelm`, `ClassifyContact`, `ReplyRequest`, `SetAutopilot`, et le pas du `MissionRunner`.

    Le moteur vit en mémoire : un changement d'état est appliqué au moteur, puis journalisé. Si le journal est
    indisponible, l'appel échoue en `database_unavailable` et l'opérateur le voit.
    """

    def __init__(
        self,
        simulator: Simulator,
        journal: MissionJournal,
        clock: Clock,
        runner_period_s: float,
        signal_table: KB | None = None,
    ) -> None:
        self._simulator = simulator
        self._journal = journal
        self._clock = clock
        self._signal_table = signal_table
        self._runner_period_s = runner_period_s
        self._runs_by_id: dict[str, MissionRun] = {}

    async def run(
        self,
        mission_id: str,
        document: dict[str, Any],
        player_ship: str,
        *,
        operator: str,
        autopilot: bool,
        manual_helm: bool,
        speed_kn: tuple[int, int],
    ) -> MissionRun:
        """`RunMission` : déroule la photo envoyée par le back-office ; rejoué, rend la mission lancée."""
        if (existing := self._runs_by_id.get(mission_id)) is not None:
            return existing
        try:
            scenario = load(document)
            speed = SpeedLimits(*speed_kn)
        except (ScenarioError, ValueError) as error:
            raise InvalidScenario(errors=error.args) from error
        scenario_id = str(scenario["id"])
        if player_ship not in {ship["nom"] for ship in scenario["flotte"]}:
            raise UnknownShip(ship=player_ship)
        if any(run.active for run in self._runs_by_id.values()):
            raise MissionAlreadyRunning
        initial_heading_deg = float(scenario.get("cap_initial", 0))
        await self._simulator.clear()
        await self._simulator.spawn(
            {
                name: (east_m, north_m, initial_heading_deg)
                for name, (east_m, north_m) in ScenarioEngine.initial_positions(scenario).items()
            }
        )
        engine = ScenarioEngine(
            scenario,
            player_ship,
            clock=self._clock,
            rng=random.Random(),  # noqa: S311 — tirage d'exercice, pas de la cryptographie
            auto=autopilot,
            manual=manual_helm,
            signal_table=self._signal_table,
            speed=speed,
        )
        engine.st = await self._simulator.states()
        run = MissionRun(mission_id, scenario_id, operator, engine)
        await self._journal.mission_started(
            run.id,
            scenario_id,
            player_ship,
            operator,
            AuditEntry(
                AuditEvent.MISSION_STARTED,
                operator,
                run.id,
                {"scenario_id": scenario_id, "player_ship": player_ship, "autopilot": autopilot},
                FactType.MISSION_STARTED,
            ),
        )
        self._runs_by_id[run.id] = run
        if self._runner_period_s > 0:
            run.task = asyncio.create_task(self._run_until_end(run), name=f"mission-{run.id}")
        log.info(
            "mission_started",
            mission_id=run.id,
            scenario_id=scenario_id,
            player_ship=player_ship,
            operator=operator,
        )
        return run

    async def advance(self, mission_id: str) -> None:
        """Un pas du `MissionRunner` : état du monde, moteur, points de route envoyés au simulateur."""
        run = self.read(mission_id)
        if not run.active:
            return
        waypoints = run.engine.tick(await self._simulator.states())
        if waypoints:
            await self._simulator.steer(waypoints)
        if run.ended:
            await self._finish(run, MissionOutcome.FINISHED, actor_id=None)

    async def _finish(self, run: MissionRun, outcome: MissionOutcome, actor_id: str | None) -> None:
        debrief = run.engine.run["debrief"]
        await self._journal.mission_finished(
            run.id,
            outcome,
            debrief,
            AuditEntry(
                AuditEvent.MISSION_FINISHED,
                actor_id,
                run.id,
                {"outcome": outcome.value, "debrief": debrief},
                FactType.MISSION_FINISHED,
            ),
        )
        log.info("mission_finished", mission_id=run.id, outcome=outcome.value)

    async def _run_until_end(self, run: MissionRun) -> None:
        while run.active:
            try:
                await self.advance(run.id)
            except Exception:
                log.exception("mission_step_failed", mission_id=run.id)
            await asyncio.sleep(self._runner_period_s)

    def read(self, mission_id: str) -> MissionRun:
        run = self._runs_by_id.get(mission_id)
        if run is None:
            raise MissionNotFound(mission_id=mission_id)
        return run

    def _read_active(self, mission_id: str) -> MissionRun:
        run = self.read(mission_id)
        if not run.active:
            raise MissionEnded(mission_id=mission_id)
        return run

    async def stop(self, mission_id: str, *, actor_id: str) -> None:
        run = self.read(mission_id)
        was_active = run.active
        run.stopped = True
        if run.task is not None:
            run.task.cancel()
        await self._simulator.clear()
        if was_active:
            await self._finish(run, MissionOutcome.INTERRUPTED, actor_id)

    async def interrupt_unfinished(self) -> None:
        interrupted = await self._journal.interrupt_unfinished()
        if interrupted:
            log.warning("missions_interrupted_by_restart", mission_ids=interrupted)

    async def shutdown(self) -> None:
        for run in self._runs_by_id.values():
            run.stopped = True
            if run.task is not None:
                run.task.cancel()

    async def submit_order(self, mission_id: str, text: str, *, actor_id: str) -> dict[str, Any]:
        engine = self._read_active(mission_id).engine
        reading = engine.read_order(text)
        if reading["ok"]:
            engine.execute_reading(reading)
            await self._journal.record(
                AuditEntry(
                    AuditEvent.APPROVED,
                    actor_id,
                    mission_id,
                    {
                        "source": "keyboard",
                        "text_en": reading["en"],
                        "text_fr": reading["fr"],
                        **reading_summary(reading),
                    },
                    FactType.COMMAND_APPROVED,
                )
            )
        return reading

    def check_order(self, mission_id: str, text: str) -> dict[str, Any]:
        """Lecture de l'ordre (accusés, réponses, signaux MTP, syntaxe simplifiée) sans rien appliquer."""
        return self._read_active(mission_id).engine.read_order(text)

    def ship_names(self, mission_id: str) -> list[str]:
        """Indicatifs de la mission en cours, ajoutés au vocabulaire de la transcription."""
        return list(self._read_active(mission_id).engine.run["ships"])

    def is_active(self, mission_id: str) -> bool:
        run = self._runs_by_id.get(mission_id)
        return run is not None and run.active

    def apply_dispatched_order(self, mission_id: str, text: str) -> dict[str, Any]:
        """Applique au moteur un ordre que le simulateur a accepté (le pilotage vit encore dans le moteur)."""
        engine = self._read_active(mission_id).engine
        reading = engine.read_order(text)
        if reading["ok"]:
            engine.execute_reading(reading)
        return reading

    def simulate_order(self, mission_id: str, text: str) -> dict[str, Any]:
        return self.read(mission_id).engine.simulate(text)

    def recommend(self, mission_id: str) -> list[dict[str, str]]:
        return self.read(mission_id).engine.recommend()

    async def set_helm(self, mission_id: str, change: dict[str, float], *, actor_id: str) -> dict[str, Any]:
        result = self._read_active(mission_id).engine.helm(change)
        if not result["ok"]:
            raise ManualHelmInactive
        helm = dict(result["helm"])
        await self._journal.record(
            AuditEntry(
                AuditEvent.HELM,
                actor_id,
                mission_id,
                {
                    "change": change,
                    "course_deg": helm["cap"],
                    "speed_kn": helm["kn"],
                    "rudder": helm["rudder"],
                },
            )
        )
        return helm

    async def classify_contact(
        self, mission_id: str, contact_id: str, classification: str, *, actor_id: str
    ) -> None:
        if not self.read(mission_id).engine.classify(contact_id, classification):
            raise ContactNotFound(contact_id=contact_id)
        await self._journal.record(
            AuditEntry(
                AuditEvent.CONTACT_CLASSIFIED,
                actor_id,
                mission_id,
                {"contact_id": contact_id, "classification": classification},
                FactType.CONTACT_CLASSIFIED,
            )
        )

    async def reply_request(self, mission_id: str, ship: str, approve: bool, *, actor_id: str) -> str:
        result = self._read_active(mission_id).engine.reply(ship, approve)
        if not result["ok"]:
            raise NoPendingRequest(ship=ship)
        await self._journal.record(
            AuditEntry(
                AuditEvent.APPROVED if approve else AuditEvent.REJECTED,
                actor_id,
                mission_id,
                {"source": "authorization_request", "ship": ship, "text_en": result["en"]},
                FactType.COMMAND_APPROVED if approve else FactType.COMMAND_REJECTED,
            )
        )
        return str(result["en"])

    def set_autopilot(self, mission_id: str, enabled: bool) -> None:
        self._read_active(mission_id).engine.set_auto(enabled)
