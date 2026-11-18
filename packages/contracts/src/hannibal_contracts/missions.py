"""Contrats de mission (§ 12) : scénarios, mission, ordres, barre, classification, demandes."""

from enum import StrEnum
from typing import Literal

from pydantic import Field

from hannibal_contracts.base import ContractModel


class ScenarioSummary(ContractModel):
    id: str
    title: str
    level: str | None = None
    duration_s: int
    summary: str | None = None
    briefing: str | None = None
    ships: list[str] = Field(description="Navires jouables, le guide en premier")
    guide: str


class StartMission(ContractModel):
    scenario_id: str
    player: str = Field(description="Navire tenu par l'opérateur")
    autopilot: bool = Field(default=False, description="Le navire du joueur accuse et exécute seul")
    manual: bool = Field(default=False, description="Barre manuelle du navire du joueur")


class MissionPhase(StrEnum):
    RUNNING = "running"
    ENDED = "ended"


class Ship(ContractModel):
    name: str
    role: str
    x: float = Field(description="Est, en mètres, repère local du monde")
    y: float = Field(description="Nord, en mètres, repère local du monde")
    heading: float = Field(description="Cap en degrés")
    speed_mps: float
    status: str = Field(description="Libellé affiché vu par le joueur (« Vous », « En station »…)")
    status_fleet: str = Field(description="Libellé vu par la flotte")


class Classification(StrEnum):
    FRIEND = "ami"
    NEUTRAL = "neutre"
    HOSTILE = "hostile"
    UNKNOWN = "inconnu"


class Contact(ContractModel):
    id: str
    type: str
    x: float
    y: float
    course: float
    speed_kn: float
    classification: Classification
    state: str | None = None
    range_nm: float | None = None
    bearing: float | None = None
    cpa_nm: float | None = None
    tcpa_min: float | None = None


class RadioMessage(ContractModel):
    id: int
    t: float
    sender: str
    recipient: str
    en: str
    fr: str
    kind: str


class PlannedOrder(ContractModel):
    t: float
    en: str
    fr: str


class Objective(ContractModel):
    text: str
    deadline_s: float | None = None
    done: bool
    t: float | None = Field(default=None, description="Instant où l'objectif a été atteint")


class ClassificationResult(ContractModel):
    chosen: str
    actual: str


class Debrief(ContractModel):
    objectives: list[Objective]
    score: int
    total: int
    min_ship_distance_m: float | None = None
    min_cpa_nm: dict[str, float]
    classifications: dict[str, ClassificationResult]


class AuthorizationRequest(ContractModel):
    ship: str
    contact_id: str | None = None
    t: float
    fr: str


class Helm(ContractModel):
    course: float
    speed_kn: float
    rudder: int = Field(ge=-1, le=1, description="-1 bâbord, 0 droit, 1 tribord")


class Station(ContractModel):
    x: float
    y: float
    error_m: float


class Mission(ContractModel):
    id: str
    scenario_id: str
    title: str
    player: str
    guide: str
    phase: MissionPhase
    t: float = Field(description="Temps de mission en secondes")
    duration_s: float
    formation: str
    guide_course: float
    guide_speed_kn: float
    ships: list[Ship]
    contacts: list[Contact]
    messages: list[RadioMessage] = Field(description="Les 40 derniers messages radio")
    plan: list[PlannedOrder]
    pending_orders: list[str] = Field(description="Ordres reçus du guide, pas encore exécutés")
    objectives: list[Objective]
    debrief: Debrief | None = None
    autopilot: bool
    manual: bool
    helm: Helm
    station: Station | None = None
    requests: list[AuthorizationRequest]
    detached: dict[str, str] = Field(description="Navire → piste qu'il reconnaît")


class SubmitOrder(ContractModel):
    text: str = Field(min_length=1, max_length=500, description="Message MTP, ex. `ALL SHIPS TURN 30 STBD`")
    mode: Literal["direct"] = Field(
        default="direct",
        description="`direct` : émis sans revue. La revue arrive avec l'interprétation vocale.",
    )


class OrderOutcome(ContractModel):
    accepted: bool
    en: str | None = None
    fr: str | None = None
    error: str | None = Field(default=None, description="Motif du refus, lisible par l'opérateur")
    hint: str | None = None


class SetHelm(ContractModel):
    rudder: int | None = Field(default=None, ge=-1, le=1)
    course: float | None = None
    course_delta: float | None = None
    speed_kn: float | None = None
    speed_delta: float | None = None


class ClassifyContact(ContractModel):
    classification: Classification


class ReplyRequest(ContractModel):
    approve: bool


class SetAutopilot(ContractModel):
    enabled: bool


class SimulateOrder(ContractModel):
    text: str = Field(min_length=1, max_length=500)


class ContactCpa(ContractModel):
    ship: str
    contact: str
    cpa_nm: float
    tcpa_s: int
    cpa_nm_without_order: float
    risk: bool


class ShipsPassing(ContractModel):
    a: str
    b: str
    distance_m: int
    t_s: int
    risk: bool


class Simulation(ContractModel):
    accepted: bool
    error: str | None = None
    hint: str | None = None
    recipients: list[str] = Field(default_factory=list)
    fr: str | None = None
    paths: dict[str, list[tuple[float, float, int]]] = Field(
        default_factory=dict, description="Navire → points `[x, y, t]` sur 15 min"
    )
    cpa: list[ContactCpa] = Field(default_factory=list)
    ships_min: list[ShipsPassing] = Field(default_factory=list)


class Recommendation(ContractModel):
    kind: str
    text: str = Field(description="Message MTP proposé")
    reason: str
