"""Planification des missions par le back-office (Lot 7.5)."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field

from hannibal_contracts.base import ContractModel

MissionState = Literal["planned", "ready", "launching", "running", "archived"]


class ParticipantPlan(ContractModel):
    user_id: UUID
    ship: str = Field(description="Indicatif d'un navire actif de la flotte")
    game_role: str


class PlanMission(ContractModel):
    scenario_id: str = Field(description="Scénario publié ; sa version publiée est figée à la planification")
    player_ship: str
    autopilot: bool = False
    manual_helm: bool = False
    participants: list[ParticipantPlan] = Field(default_factory=list)


class ParticipantView(ContractModel):
    user_id: UUID
    username: str
    ship: str
    game_role: str


class PlannedMission(ContractModel):
    id: UUID
    scenario_id: str
    scenario_version: int = Field(ge=1)
    scenario_title: str
    player_ship: str
    autopilot: bool
    manual_helm: bool
    state: MissionState
    created_at: datetime
    launched_at: datetime | None
    archived_at: datetime | None
    run_phase: str | None = Field(
        description="Phase lue dans ops_read.mission_runs ; absente avant lancement"
    )
    finished_at: datetime | None
    participants: list[ParticipantView]


class MissionHistory(ContractModel):
    missions: list[PlannedMission] = Field(description="Plus récentes d'abord")
    next_cursor: str | None


class Player(ContractModel):
    id: UUID
    username: str


class GameRole(ContractModel):
    code: str
    label: str


class PlanningOptions(ContractModel):
    players: list[Player]
    game_roles: list[GameRole]
