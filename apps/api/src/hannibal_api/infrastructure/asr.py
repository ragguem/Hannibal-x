"""Transcripteurs : client du service `asr` (mode `real`) et transcripteur scripté (mode `fake`)."""

from collections.abc import Sequence

import httpx

from hannibal_api.application.ports import RecordingUnusable
from hannibal_api.domain.voice import HeardWord, VoiceRecording, VoiceTranscript
from hannibal_contracts.asr import Transcription
from hannibal_platform.errors import DependencyUnavailable
from hannibal_platform.internal_client import InternalClient

DEPENDENCY = "asr"


class AsrClient:
    def __init__(
        self,
        base_url: str,
        *,
        token: str | None,
        timeout_s: float,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._client = InternalClient(
            DEPENDENCY, base_url, token=token, timeout_s=timeout_s, transport=transport
        )

    async def transcribe(self, recording: VoiceRecording, ship_names: Sequence[str]) -> VoiceTranscript:
        response = await self._client.post(
            "/transcribe",
            content=recording.content,
            params=[("ship", name) for name in ship_names],
            headers={"Content-Type": recording.media_type},
        )
        if response.status_code == 422:
            raise RecordingUnusable(response.text)
        if response.status_code >= 400:
            raise DependencyUnavailable(DEPENDENCY, f"réponse {response.status_code}")
        result = Transcription.model_validate_json(response.content)
        return VoiceTranscript(
            text=result.text,
            words=[
                HeardWord(text=word.word, confidence=word.probability, start_s=word.start_s, end_s=word.end_s)
                for word in result.words
            ],
            audio_seconds=result.audio_seconds,
            transcription_seconds=result.transcription_seconds,
            model=result.model,
        )

    async def aclose(self) -> None:
        await self._client.aclose()


class ScriptedTranscriber:
    """Récite le même texte à chaque enregistrement ; `queue` permet à un test d'en imposer d'autres."""

    def __init__(self, transcript: str) -> None:
        self._default = transcript
        self.queue: list[str] = []

    async def transcribe(self, recording: VoiceRecording, ship_names: Sequence[str]) -> VoiceTranscript:
        text = self.queue.pop(0) if self.queue else self._default
        return VoiceTranscript(
            text=text,
            words=[
                HeardWord(text=word, confidence=1.0, start_s=0.5 * index, end_s=0.5 * index + 0.4)
                for index, word in enumerate(text.split())
            ],
            model="scripted",
        )
