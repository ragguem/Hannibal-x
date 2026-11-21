"""Document de scénario `schema_version: 1`, importé par le back-office et rejoué par le cœur (Lot 7).

Structure seulement : les règles qui croisent plusieurs champs (un seul guide, émetteurs connus,
pistes citées) restent dans `hannibal_core.scenario.schema.validate`. Pistes, ordres, événements,
attendus et étapes acceptent des réglages supplémentaires que le moteur sait lire.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from hannibal_contracts.base import ContractModel

OrderType = Literal["CORPEN", "TURN", "SPEED", "FORM", "RESUME", "EMERG", "ACK"]
TrackClass = Literal["ami", "neutre", "hostile", "inconnu"]


class _OpenScenarioPart(BaseModel):
    model_config = ConfigDict(extra="allow", frozen=True)


class FleetMember(ContractModel):
    nom: str = Field(min_length=1, description="Nom d'appel du navire, présent dans le catalogue")
    role: Literal["guide", "escorte"]


class ScenarioOrder(_OpenScenarioPart):
    type: OrderType
    cap: float | None = None
    deg: float | None = None
    side: str | None = None
    kn: float | None = None
    name: str | None = None
    text: str | None = None


class ScenarioTrack(_OpenScenarioPart):
    id: str = Field(min_length=1)
    type: str
    rel: float = Field(description="Relèvement relatif au guide, en degrés")
    dist_nm: float
    cap: float
    vit_kn: float
    cls_reel: TrackClass = "inconnu"
    comportement: str | None = None
    rapports_nm: list[float] = Field(default_factory=list)


class ScenarioEvent(_OpenScenarioPart):
    t: float | None = None
    de: str | None = None
    a: str | None = Field(default=None, description="Nom d'un navire ou `TOUS`")
    ordres: list[ScenarioOrder] | None = None
    piste: ScenarioTrack | None = None
    apres_repousse: str | None = None
    delai_s: float | None = None


class ScenarioGoal(_OpenScenarioPart):
    texte: str = Field(min_length=1)
    avant_t: float | None = None
    ordre: OrderType | None = None
    classe: str | None = None
    cls: TrackClass | None = None
    repousse: str | None = None
    garde_nm: float | None = None
    piste: str | None = None


class ScenarioStep(_OpenScenarioPart):
    key: str | None = None
    ordre: str | None = None
    texte: str | None = None
    rel_tens: list[float] | None = None


class ScenarioDocument(ContractModel):
    schema_version: Literal[1]
    id: str = Field(min_length=1, pattern=r"^[a-z0-9_]+$")
    titre: str = Field(min_length=1)
    niveau: str = Field(min_length=1)
    duree_s: float = Field(gt=0)
    resume: str = Field(min_length=1)
    briefing: str = Field(min_length=1)
    formation_depart: str = "column"
    cap_initial: float | None = None
    vitesse_initiale_kn: float | None = None
    flotte: list[FleetMember] = Field(min_length=1)
    evenements: list[ScenarioEvent] = Field(default_factory=list)
    attendu: list[ScenarioGoal] = Field(default_factory=list)
    etapes: list[ScenarioStep] | None = Field(default=None, min_length=1)
    etapes_aleatoires: int | None = Field(default=None, ge=1)
    etapes_delai_s: float | None = None
