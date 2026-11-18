"""Contrat interne API → `sim-bridge`. Positions en mètres dans le repère local (x à l'est, y au nord)."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class _Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ShipPlacement(_Contract):
    name: str = Field(min_length=1, max_length=64)
    east_m: float
    north_m: float
    heading_deg: float = Field(ge=0, lt=360)


class SpawnFleet(_Contract):
    """Remplace la flotte du monde : les navires existants sont retirés, ceux-ci créés."""

    ships: list[ShipPlacement] = Field(min_length=1, max_length=16)


class GeoWaypoint(_Contract):
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)


class SteerFleet(_Contract):
    """Points de route du pas de pilotage, un par navire, envoyés en un seul appel."""

    waypoints: dict[str, GeoWaypoint]


class ShipState(_Contract):
    x: float
    y: float
    lat: float
    lon: float
    sog: float = Field(description="Vitesse fond, m/s")
    hdg: float = Field(description="Cap vrai, degrés")


class WorldState(_Contract):
    ships: dict[str, ShipState]


class RecordManeuver(_Contract):
    command_id: str = Field(min_length=1, max_length=64)
    maneuver: dict[str, Any]


class ManeuverRecord(_Contract):
    command_id: str
    maneuver: dict[str, Any]
    recorded_at: datetime
