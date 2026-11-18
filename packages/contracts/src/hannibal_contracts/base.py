from pydantic import BaseModel, ConfigDict


class ContractModel(BaseModel):
    """Base de tout modèle échangé : champ inconnu refusé, instance immuable."""

    model_config = ConfigDict(extra="forbid", frozen=True)
