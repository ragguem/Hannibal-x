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
    signal_table_path: Path | None = Field(
        default=None,
        description="Table MTP (`signals.json`) hors dépôt ; sans elle, seule la syntaxe simplifiée est lue",
    )
    mission_runner_period_s: float = Field(default=0.5, ge=0, description="Pas du MissionRunner ; 0 le coupe")
    mission_stream_period_s: float = Field(
        default=0.25, gt=0, description="Rythme des événements `situation`"
    )
    simulator_origin_lat_lon: tuple[float, float] = (43.0, 6.0)
    sim_bridge_url: str | None = Field(
        default=None, description="Sans URL, chaque appel échoue en transitoire"
    )
    sim_bridge_timeout_s: float = Field(default=2.0, gt=0)
    command_validity_s: float = Field(
        default=30.0, gt=0, description="Après la décision, délai au-delà duquel un ordre n'est plus envoyé"
    )
    dispatch_max_attempts: int = Field(default=5, ge=1)
    dispatch_attempt_timeout_s: float = Field(default=5.0, gt=0)
    dispatch_poll_period_s: float = Field(
        default=0.5, ge=0, description="Réveil du répartiteur sans notification ; 0 le désactive (tests)"
    )

    asr_url: str | None = Field(default=None, description="Sans URL, un ordre vocal échoue en `503`")
    asr_timeout_s: float = Field(default=30.0, gt=0, description="Couvre le chargement à froid du modèle")
    recordings_dir: Path = Field(
        default=Path("/var/lib/hannibal/recordings"),
        description="Volume des enregistrements vocaux (mode `real`), hors dépôt",
    )
    min_recording_bytes: int = Field(default=2000, ge=0, description="En dessous : enregistrement trop court")
    max_recording_bytes: int = Field(default=10 * 1024 * 1024, gt=0)
    scripted_transcript: str = Field(
        default="ALL SHIPS CORPEN 045 SPEED 12", description="Ce que « entend » le mode `fake`"
    )

    doctrine_url: str | None = Field(
        default=None, description="Sans URL, une question de doctrine échoue en `503`"
    )
    doctrine_timeout_s: float = Field(
        default=120.0, gt=0, description="Couvre second essai et modèle de repli"
    )
    doctrine_active: int = Field(
        default=1, ge=1, description="Questions traitées en même temps (GPU partagé)"
    )
    doctrine_waiting: int = Field(default=2, ge=0, description="Questions en attente ; au-delà : `429`")
    doctrine_wait_s: float = Field(
        default=20.0, gt=0, description="Attente maximale d'un tour ; au-delà : `429`"
    )
    voice_active: int = Field(default=1, ge=1, description="Transcriptions en même temps (GPU partagé)")
    voice_waiting: int = Field(default=3, ge=0, description="Transcriptions en attente ; au-delà : `429`")
    voice_wait_s: float = Field(default=10.0, gt=0, description="Attente maximale d'une transcription")

    @property
    def doctrine_base_url(self) -> str:
        return self.doctrine_url.rstrip("/") if self.doctrine_url else ""

    @property
    def doctrine_health_url(self) -> str | None:
        return f"{self.doctrine_base_url}/health" if self.doctrine_url else None

    @property
    def asr_base_url(self) -> str:
        return self.asr_url.rstrip("/") if self.asr_url else ""

    @property
    def asr_health_url(self) -> str | None:
        return f"{self.asr_base_url}/health" if self.asr_url else None

    @property
    def database_dsn(self) -> str | None:
        return self.database_url.get_secret_value() if self.database_url else None

    @property
    def internal_token_value(self) -> str | None:
        return self.internal_token.get_secret_value() if self.internal_token else None

    @property
    def sim_bridge_base_url(self) -> str:
        return self.sim_bridge_url.rstrip("/") if self.sim_bridge_url else ""

    @property
    def sim_bridge_health_url(self) -> str | None:
        return f"{self.sim_bridge_base_url}/health" if self.sim_bridge_url else None

    @property
    def ollama_health_url(self) -> str | None:
        return f"{self.ollama_url.rstrip('/')}/api/version" if self.ollama_url else None
