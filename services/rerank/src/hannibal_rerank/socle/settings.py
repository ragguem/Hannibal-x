from enum import StrEnum

from pydantic import Field
from pydantic_settings import SettingsConfigDict

from hannibal_platform.settings import BaseServiceSettings


class ScorerKind(StrEnum):
    CROSS_ENCODER = "cross_encoder"
    LEXICAL = "lexical"


class RerankSettings(BaseServiceSettings):
    model_config = SettingsConfigDict(env_prefix="HX_RERANK_", extra="ignore", frozen=True)

    service_name: str = "rerank"
    scorer: ScorerKind = Field(
        default=ScorerKind.CROSS_ENCODER,
        description="`lexical` : mots communs, sans modèle (poste sans GPU, tests)",
    )
    model: str = Field(
        default="BAAI/bge-reranker-v2-m3", description="Nom Hugging Face ou dossier local (reranker-hannibal)"
    )
    device: str = "cuda"
    half_precision: bool = Field(default=True, description="Sur GPU seulement : environ 1,5 Go de VRAM")
    batch_size: int = Field(default=16, ge=1)
    max_length: int = Field(default=512, ge=32)
    max_queries: int = Field(default=3, ge=1)
    max_passages: int = Field(default=60, ge=1)
    max_passage_chars: int = Field(default=4000, ge=100)
