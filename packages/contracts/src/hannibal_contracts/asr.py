"""Contrat interne `api` → `asr` : `POST /transcribe` (corps = audio brut, vocabulaire en paramètres)."""

from pydantic import Field

from hannibal_contracts.base import ContractModel


class TranscribedWord(ContractModel):
    word: str
    probability: float = Field(ge=0, le=1)
    start_s: float
    end_s: float


class Transcription(ContractModel):
    text: str = Field(description="Transcription complète, segments joints par une espace")
    words: list[TranscribedWord]
    audio_seconds: float = Field(description="Durée de l'audio reçu")
    transcription_seconds: float = Field(description="Temps de calcul de la transcription")
    model: str = Field(description="Modèle Whisper effectivement chargé (repli compris)")
