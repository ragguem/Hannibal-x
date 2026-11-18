from enum import StrEnum
from pathlib import Path

from pydantic import Field
from pydantic_settings import SettingsConfigDict

from hannibal_platform.settings import BaseServiceSettings


class WorldKind(StrEnum):
    KINEMATIC = "kinematic"
    ROS = "ros"


class SimBridgeSettings(BaseServiceSettings):
    model_config = SettingsConfigDict(env_prefix="HX_SIM_BRIDGE_", extra="ignore", frozen=True)

    service_name: str = "sim-bridge"
    world: WorldKind = WorldKind.ROS
    origin_lat_lon: tuple[float, float] = Field(
        default=(43.0, 6.0), description="Origine du repère local du monde cinématique"
    )
    lotusim_world: str = "defenseScenario"
    vessel_model: str = "fremm"
    command_timeout_s: float = Field(default=20.0, gt=0)
    registry_path: Path | None = Field(
        default=None, description="Journal des manœuvres reçues ; sans chemin, le registre est en mémoire"
    )
