from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class HeardWord:
    text: str
    probability: float
    start_s: float
    end_s: float


@dataclass(frozen=True, slots=True)
class EngineTranscript:
    text: str
    words: list[HeardWord]
    audio_seconds: float


class UnreadableAudio(Exception):
    """Le moteur ne sait pas décoder le fichier reçu."""


class SpeechEngine(Protocol):
    """Moteur de reconnaissance vocale. Bloquant : le handler l'appelle hors de la boucle d'événements."""

    @property
    def model_name(self) -> str: ...

    def transcribe(self, audio: bytes, vocabulary_prompt: str) -> EngineTranscript: ...
