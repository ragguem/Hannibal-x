"""Contrats de mission (§ 12) : scénarios, mission, ordres, barre, classification, demandes.

Unités dans le nom du champ : `_m` mètres, `_nm` milles nautiques, `_kn` nœuds,
`_mps` mètres par seconde, `_deg` degrés, `_s` secondes de mission, `_min` minutes.
Positions : `east_m` et `north_m` dans le repère local du monde.
CPA : distance au point de rapprochement maximal ; TCPA : temps restant avant ce point.
"""

from enum import StrEnum
from uuid import UUID

from pydantic import Field

from hannibal_contracts.base import ContractModel


class ScenarioSummary(ContractModel):
    id: str
    title: str
    level: str | None = None
    duration_s: int
    summary: str | None = None
    briefing: str | None = None
    playable_ships: list[str] = Field(description="Navires que l'opérateur peut tenir, le guide en premier")
    guide_ship: str


class StartMission(ContractModel):
    scenario_id: str
    player_ship: str = Field(description="Navire tenu par l'opérateur")
    autopilot: bool = Field(default=False, description="Le navire du joueur accuse et exécute seul")
    manual_helm: bool = Field(default=False, description="Le joueur tient la barre de son navire")


class MissionPhase(StrEnum):
    RUNNING = "running"
    ENDED = "ended"


class Ship(ContractModel):
    name: str
    role: str
    east_m: float
    north_m: float
    heading_deg: float
    speed_mps: float
    status_for_player: str = Field(description="Libellé vu par le joueur (« Vous », « En station »…)")
    status_for_fleet: str = Field(description="Libellé vu par le reste de la flotte")


class Classification(StrEnum):
    FRIEND = "ami"
    NEUTRAL = "neutre"
    HOSTILE = "hostile"
    UNKNOWN = "inconnu"


class Contact(ContractModel):
    id: str
    category: str = Field(description="Surface, aérien…")
    east_m: float
    north_m: float
    course_deg: float
    speed_kn: float
    classification: Classification
    behaviour: str | None = Field(
        default=None, description="Comportement courant de la piste, s'il est connu"
    )
    range_nm: float | None = Field(default=None, description="Distance au navire du joueur")
    bearing_deg: float | None = Field(default=None, description="Relèvement depuis le navire du joueur")
    cpa_nm: float | None = None
    tcpa_min: float | None = None


class RadioMessage(ContractModel):
    id: int
    sent_at_s: float
    sender: str
    recipient: str
    text_en: str = Field(description="Message tel qu'émis sur la radio")
    text_fr: str = Field(description="Traduction pour l'opérateur")
    kind: str


class PlannedOrder(ContractModel):
    planned_at_s: float
    text_en: str
    text_fr: str


class Objective(ContractModel):
    description: str
    deadline_s: float | None = None
    achieved: bool
    achieved_at_s: float | None = None


class ClassificationResult(ContractModel):
    chosen: str
    actual: str


class Debrief(ContractModel):
    objectives: list[Objective]
    score: int
    objectives_total: int
    closest_ships_distance_m: float | None = Field(
        default=None, description="Plus petite distance entre deux navires"
    )
    closest_cpa_nm_by_contact: dict[str, float]
    classification_by_contact: dict[str, ClassificationResult]


class AuthorizationRequest(ContractModel):
    ship: str
    contact_id: str | None = None
    requested_at_s: float
    text_fr: str


class Helm(ContractModel):
    course_deg: float
    speed_kn: float
    rudder: int = Field(ge=-1, le=1, description="-1 bâbord, 0 droit, 1 tribord")


class Station(ContractModel):
    east_m: float
    north_m: float
    offset_m: float = Field(description="Écart entre le navire et son poste dans la formation")


class Mission(ContractModel):
    id: str
    scenario_id: str
    title: str
    player_ship: str
    guide_ship: str
    phase: MissionPhase
    elapsed_s: float
    duration_s: float
    formation: str
    guide_course_deg: float
    guide_speed_kn: float
    ships: list[Ship]
    contacts: list[Contact]
    radio_messages: list[RadioMessage] = Field(description="Les 40 derniers messages radio")
    planned_orders: list[PlannedOrder]
    pending_orders: list[str] = Field(description="Ordres reçus du guide, pas encore exécutés")
    objectives: list[Objective]
    debrief: Debrief | None = None
    autopilot: bool
    manual_helm: bool
    helm: Helm
    station: Station | None = Field(default=None, description="Poste du joueur, absent s'il est guide")
    authorization_requests: list[AuthorizationRequest]
    reconnaissance_target_by_ship: dict[str, str] = Field(
        description="Navire détaché → piste qu'il reconnaît"
    )


class OrderMode(StrEnum):
    DIRECT = "direct"
    REVIEW = "review"


class CommandState(StrEnum):
    AWAITING_REVIEW = "awaiting_review"
    REJECTED = "rejected"
    DISPATCHING = "dispatching"
    DISPATCHED = "dispatched"
    DISPATCH_FAILED = "dispatch_failed"


class SubmitOrder(ContractModel):
    text: str = Field(min_length=1, max_length=500, description="Message MTP, ex. `ALL SHIPS TURN 30 STBD`")
    mode: OrderMode = Field(
        default=OrderMode.DIRECT,
        description="`direct` : émis sans revue. `review` : attend `POST /commands/{id}/decision`.",
    )
    parent_id: UUID | None = Field(default=None, description="Commande que cet ordre corrige (mode `review`)")


class OrderOutcome(ContractModel):
    accepted: bool
    text_en: str | None = None
    text_fr: str | None = None
    refusal_reason: str | None = Field(default=None, description="Motif du refus, lisible par l'opérateur")
    hint: str | None = None
    command_id: UUID | None = Field(default=None, description="Commande créée en mode `review`")
    command_state: CommandState | None = None


class HeardWord(ContractModel):
    word: str
    confidence: float = Field(ge=0, le=1, description="Probabilité du mot selon le modèle de transcription")
    start_s: float
    end_s: float


class VoiceOrderOutcome(OrderOutcome):
    """`POST /missions/{id}/voice` : ce qui a été entendu, puis la même interprétation qu'au clavier."""

    recording_id: UUID = Field(
        description="Identifiant de l'enregistrement ; celui de la commande si elle est créée"
    )
    transcript: str = Field(description="Texte entendu, avant interprétation")
    heard_words: list[HeardWord]
    transcription_seconds: float = Field(description="Durée de la transcription côté serveur")


class CommandSource(StrEnum):
    KEYBOARD = "keyboard"
    VOICE = "voice"


class CommandDecision(StrEnum):
    APPROVE = "approve"
    REJECT = "reject"
    RETRY = "retry"


class DecideCommand(ContractModel):
    decision: CommandDecision = Field(
        description="`retry` : renvoyer une commande `dispatch_failed` avant son échéance de validité"
    )


class Command(ContractModel):
    id: UUID
    mission_id: UUID
    text: str
    text_en: str
    text_fr: str
    state: CommandState
    source: CommandSource = CommandSource.KEYBOARD
    submitted_by: str
    decided_by: str | None = None
    parent_id: UUID | None = None
    last_error: str | None = Field(default=None, description="Motif du dernier échec d'envoi")


class SetHelm(ContractModel):
    rudder: int | None = Field(default=None, ge=-1, le=1)
    course_deg: float | None = None
    course_change_deg: float | None = None
    speed_kn: float | None = None
    speed_change_kn: float | None = None


class ClassifyContact(ContractModel):
    classification: Classification


class ReplyRequest(ContractModel):
    approve: bool


class SetAutopilot(ContractModel):
    enabled: bool


class SimulateOrder(ContractModel):
    text: str = Field(min_length=1, max_length=500)


class TrackPoint(ContractModel):
    east_m: float
    north_m: float
    at_s: int


class ContactCpa(ContractModel):
    ship: str
    contact_id: str
    cpa_nm: float
    tcpa_s: int
    cpa_nm_without_order: float
    at_risk: bool = Field(description="CPA inférieur à 0,5 NM")


class ShipsPassing(ContractModel):
    ship_a: str
    ship_b: str
    distance_m: int
    at_s: int
    at_risk: bool = Field(description="Distance inférieure à 150 m")


class Simulation(ContractModel):
    accepted: bool
    refusal_reason: str | None = None
    hint: str | None = None
    recipients: list[str] = Field(default_factory=list)
    text_fr: str | None = None
    track_by_ship: dict[str, list[TrackPoint]] = Field(
        default_factory=dict, description="Trajectoire sur 15 min"
    )
    contact_cpas: list[ContactCpa] = Field(default_factory=list)
    ships_passings: list[ShipsPassing] = Field(default_factory=list)


class Recommendation(ContractModel):
    kind: str
    text: str = Field(description="Message MTP proposé")
    reason: str
