from enum import StrEnum
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import SettingsConfigDict

from hannibal_platform.settings import BaseServiceSettings


class AdapterMode(StrEnum):
    FAKE = "fake"
    REAL = "real"


class ApiSettings(BaseServiceSettings):
    model_config = SettingsConfigDict(env_prefix="HX_API_", extra="ignore", frozen=True)

    service_name: str = "api"
    adapters: AdapterMode = AdapterMode.REAL
    database_url: SecretStr | None = None
    ollama_url: str | None = None
    readiness_timeout_s: float = 2.0
    scenarios_dir: Path = Path(__file__).resolve().parents[3] / "scenarios"
    mission_runner_period_s: float = Field(default=0.5, ge=0, description="Pas du MissionRunner ; 0 le coupe")
    mission_stream_period_s: float = Field(
        default=0.25, gt=0, description="Rythme des événements `situation`"
    )
    simulator_origin_lat_lon: tuple[float, float] = (43.0, 6.0)
    command_validity_s: float = Field(
        default=30.0, gt=0, description="Après la décision, délai au-delà duquel un ordre n'est plus envoyé"
    )
    dispatch_max_attempts: int = Field(default=5, ge=1)
    dispatch_attempt_timeout_s: float = Field(default=5.0, gt=0)
    dispatch_poll_period_s: float = Field(
        default=0.5, ge=0, description="Réveil du répartiteur sans notification ; 0 le désactive (tests)"
    )

    @property
    def database_dsn(self) -> str | None:
        return self.database_url.get_secret_value() if self.database_url else None

    @property
    def ollama_health_url(self) -> str | None:
        return f"{self.ollama_url.rstrip('/')}/api/version" if self.ollama_url else None
