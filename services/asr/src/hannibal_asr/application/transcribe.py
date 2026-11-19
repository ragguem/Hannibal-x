"""Handler `TranscribeRecording` : un enregistrement, le vocabulaire du domaine, les navires de la mission."""

import asyncio
import time
from collections.abc import Sequence
from dataclasses import dataclass

from hannibal_asr.application.ports import EngineTranscript, SpeechEngine, UnreadableAudio
from hannibal_platform.logging import get_logger

log = get_logger(__name__)

DOMAIN_VOCABULARY = (
    "NATO maritime tactical signals. This is, over, out, execute to follow, immediate "
    "execute, I say again, standby, execute. Corpen, turn, speed, station, screen, "
    "formation, emergency, interrogative, desig, negat, tack, answer, port, starboard. "
    "Alfa, Bravo, Charlie, Delta, Echo, Foxtrot, Golf, Hotel, India, Juliett, Kilo, Lima, "
    "Mike, November, Oscar, Papa, Quebec, Romeo, Sierra, Tango, Uniform, Victor, Whiskey, "
    "Xray, Yankee, Zulu. Zero, one, two, three, four, five, six, seven, eight, niner. "
    "Hannibal, all ships."
)
MAX_SHIP_NAMES = 20


class RecordingRejected(Exception):
    """Trop court, trop long ou illisible : l'appelant reçoit un `422`, jamais une erreur de dépendance."""


@dataclass(frozen=True, slots=True)
class RecordingTranscript:
    transcript: EngineTranscript
    transcription_seconds: float
    model: str


def vocabulary_prompt(ship_names: Sequence[str]) -> str:
    """Le vocabulaire fixe, puis les indicatifs de la mission que Whisper ne connaît pas."""
    names = [name.strip().capitalize() for name in ship_names if name.strip()][:MAX_SHIP_NAMES]
    return f"{DOMAIN_VOCABULARY} {', '.join(names)}." if names else DOMAIN_VOCABULARY


class TranscribeRecording:
    """Un seul calcul à la fois : le modèle occupe le GPU partagé avec Ollama."""

    def __init__(self, engine: SpeechEngine, *, min_audio_bytes: int, max_audio_bytes: int) -> None:
        self._engine = engine
        self._min_audio_bytes = min_audio_bytes
        self._max_audio_bytes = max_audio_bytes
        self._engine_lock = asyncio.Lock()

    @property
    def model_name(self) -> str:
        return self._engine.model_name

    async def __call__(self, audio: bytes, ship_names: Sequence[str]) -> RecordingTranscript:
        if not self._min_audio_bytes <= len(audio) <= self._max_audio_bytes:
            raise RecordingRejected(f"taille {len(audio)} octets")
        prompt = vocabulary_prompt(ship_names)
        async with self._engine_lock:
            started = time.perf_counter()
            try:
                transcript = await asyncio.to_thread(self._engine.transcribe, audio, prompt)
            except UnreadableAudio as error:
                raise RecordingRejected(str(error)) from error
            elapsed = time.perf_counter() - started
        log.info(
            "recording_transcribed",
            audio_seconds=transcript.audio_seconds,
            transcription_seconds=round(elapsed, 3),
            model=self._engine.model_name,
        )
        return RecordingTranscript(transcript, round(elapsed, 3), self._engine.model_name)
