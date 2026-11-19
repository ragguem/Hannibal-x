"""Moteur sans modèle : poste de développement sans GPU et tests. Il n'écoute pas, il récite."""

import io
import wave

from hannibal_asr.application.ports import EngineTranscript, HeardWord


def wav_duration_s(audio: bytes) -> float:
    try:
        with wave.open(io.BytesIO(audio), "rb") as recording:
            return round(recording.getnframes() / recording.getframerate(), 2)
    except (wave.Error, EOFError):
        return 0.0


class ScriptedSpeechEngine:
    def __init__(self, transcript: str) -> None:
        self._transcript = transcript

    @property
    def model_name(self) -> str:
        return "scripted"

    def transcribe(self, audio: bytes, vocabulary_prompt: str) -> EngineTranscript:
        words = self._transcript.split()
        return EngineTranscript(
            text=self._transcript,
            words=[
                HeardWord(text=word, probability=1.0, start_s=0.5 * index, end_s=0.5 * index + 0.4)
                for index, word in enumerate(words)
            ],
            audio_seconds=wav_duration_s(audio),
        )
