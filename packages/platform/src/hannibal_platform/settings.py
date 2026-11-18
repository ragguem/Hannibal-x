from enum import StrEnum

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(StrEnum):
    DEV = "dev"
    TEST = "test"
    INTEGRATION = "integration"
    PRODUCTION = "production"


class BaseServiceSettings(BaseSettings):
    """Configuration commune. Chaque processus hérite et fixe son préfixe (`HX_API_`, `HX_ASR_`, …)."""

    model_config = SettingsConfigDict(env_prefix="HX_", env_file=None, extra="ignore", frozen=True)

    service_name: str = "hannibal"
    environment: Environment = Environment.DEV
    log_level: str = "INFO"
    log_json: bool = True
    internal_token: SecretStr | None = None
    metrics_token: SecretStr | None = None

    @property
    def is_local(self) -> bool:
        return self.environment in (Environment.DEV, Environment.TEST)
