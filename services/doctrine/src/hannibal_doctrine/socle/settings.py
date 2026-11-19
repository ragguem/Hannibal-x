from enum import StrEnum

from pydantic import Field, SecretStr
from pydantic_settings import SettingsConfigDict

from hannibal_platform.settings import BaseServiceSettings


class DoctrineAdapters(StrEnum):
    REAL = "real"
    SAMPLE = "sample"


class AnswerStyle(StrEnum):
    VERIFY = "verify"
    QUOTES = "quotes"


class DoctrineSettings(BaseServiceSettings):
    """Réglages du pipeline. Les seuils sont renvoyés dans chaque réponse et gardés dans `doctrine_traces`."""

    model_config = SettingsConfigDict(env_prefix="HX_DOCTRINE_", extra="ignore", frozen=True)

    service_name: str = "doctrine"
    adapters: DoctrineAdapters = Field(
        default=DoctrineAdapters.REAL,
        description="`sample` : corpus inventé, modèle scripté, sans base ni GPU",
    )
    database_url: SecretStr | None = Field(
        default=None, description="Rôle `hannibal_doctrine` (SELECT sur `v2`) ; aucun mot de passe par défaut"
    )
    ollama_url: str = "http://ollama:11434"
    drafting_model: str = "gemma3:12b"
    fallback_model: str = Field(default="", description="Second rédacteur, appelé seulement après deux refus")
    embedding_model: str = "bge-m3"
    embeddings_on_cpu: bool = False
    reasoning: bool | None = Field(
        default=None, description="`false` coupe le raisonnement des modèles qwen3…"
    )
    retry_with_reasoning: bool = False
    context_window: int = Field(default=8192, ge=2048)
    chat_timeout_s: float = Field(default=300.0, gt=0)
    embedding_timeout_s: float = Field(default=120.0, gt=0)
    rerank_url: str | None = Field(
        default=None, description="Sans URL : ordre des vecteurs, sans reclassement"
    )
    rerank_timeout_s: float = Field(default=8.0, gt=0)
    classified_publications: list[str] = Field(
        default_factory=lambda: ["ATP-28"], description="Exclues sauf permission `doctrine:classified`"
    )
    min_similarity: float = Field(default=0.45, ge=0, le=1, description="Couverture : en dessous, refus")
    extracts: int = Field(default=10, ge=1, le=30)
    retry_extracts: int = Field(default=3, ge=0, le=10)
    answer_style: AnswerStyle = AnswerStyle.VERIFY
    use_table_rows: bool = False
    use_generated_questions: bool = False
    grounding_check: bool = True
    whole_word_acronyms: bool = False

    @property
    def database_dsn(self) -> str | None:
        return self.database_url.get_secret_value() if self.database_url else None
