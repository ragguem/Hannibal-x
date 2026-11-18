from enum import StrEnum

from pydantic import SecretStr
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

    @property
    def database_dsn(self) -> str | None:
        return self.database_url.get_secret_value() if self.database_url else None

    @property
    def ollama_health_url(self) -> str | None:
        return f"{self.ollama_url.rstrip('/')}/api/version" if self.ollama_url else None
