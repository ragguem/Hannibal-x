"""Contrat interne `doctrine` → `rerank` : `POST /rerank`."""

from pydantic import Field

from hannibal_contracts.base import ContractModel


class RerankRequest(ContractModel):
    queries: list[str] = Field(
        min_length=1, max_length=3, description="Question d'origine et sa reformulation anglaise"
    )
    passages: list[str] = Field(max_length=60, description="Textes à classer, tronqués côté service")


class RerankResponse(ContractModel):
    scores: list[float] = Field(description="Meilleur score sur les requêtes, un par passage, même ordre")
    model: str
