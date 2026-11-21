"""Catalogue des navires du back-office (Lot 7.3), réservé à la permission `catalog:manage`."""

from datetime import datetime
from uuid import UUID

from pydantic import Field

from hannibal_contracts.base import ContractModel

CLASS_CODE = r"^[a-z][a-z0-9_-]{1,31}$"
CALL_SIGN = r"^[a-z][a-z0-9-]{1,23}$"


class ShipClassFields(ContractModel):
    label: str = Field(min_length=1, max_length=64)
    min_speed_knots: int = Field(gt=0, le=60, description="Vitesse minimale ordonnable, en nœuds")
    max_speed_knots: int = Field(gt=0, le=60, description="Vitesse maximale ordonnable, en nœuds")
    turn_radius_meters: float = Field(gt=0, le=5000)
    length_meters: float = Field(gt=0, le=500)


class ShipClass(ShipClassFields):
    code: str = Field(pattern=CLASS_CODE)


class ShipClassList(ContractModel):
    classes: list[ShipClass] = Field(description="Toutes les classes, par code")


class UpdateShipClass(ShipClassFields):
    pass


class ShipView(ContractModel):
    id: UUID
    call_sign: str = Field(pattern=CALL_SIGN, description="Nom d'appel, celui des flottes des scénarios")
    class_code: str
    active: bool = Field(description="Faux une fois retiré : plus proposé à la planification")
    created_at: datetime
    retired_at: datetime | None


class ShipList(ContractModel):
    ships: list[ShipView] = Field(description="Tous les navires, par nom d'appel")


class CreateShip(ContractModel):
    call_sign: str = Field(pattern=CALL_SIGN)
    class_code: str


class ChangeShipClass(ContractModel):
    class_code: str
