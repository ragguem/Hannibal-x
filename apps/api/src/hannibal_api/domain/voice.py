"""Ordre vocal (§ 7) : l'enregistrement gardé pour le registre et ce que la transcription en a tiré."""

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class HeardWord:
    text: str
    confidence: float
    start_s: float
    end_s: float


@dataclass(frozen=True, slots=True)
class VoiceTranscript:
    text: str
    words: list[HeardWord] = field(default_factory=list)
    audio_seconds: float = 0.0
    transcription_seconds: float = 0.0
    model: str = ""

    def audit_payload(self) -> dict[str, Any]:
        return {
            "source": "voice",
            "transcript": self.text,
            "words": [
                {"w": word.text, "p": word.confidence, "t0": word.start_s, "t1": word.end_s}
                for word in self.words
            ],
            "audio_seconds": self.audio_seconds,
            "transcription_seconds": self.transcription_seconds,
            "asr_model": self.model,
            "audio": True,
        }


@dataclass(frozen=True, slots=True)
class VoiceRecording:
    content: bytes
    media_type: str
