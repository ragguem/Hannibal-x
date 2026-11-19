"""Enregistrements vocaux : un fichier par commande sur le volume, ou en mémoire (mode `fake`)."""

import asyncio
import uuid
from pathlib import Path

from hannibal_api.domain.voice import VoiceRecording

EXTENSION_BY_MEDIA_TYPE = {
    "audio/wav": "wav",
    "audio/x-wav": "wav",
    "audio/wave": "wav",
    "audio/webm": "webm",
    "audio/ogg": "ogg",
    "audio/mpeg": "mp3",
}
MEDIA_TYPE_BY_EXTENSION = {"wav": "audio/wav", "webm": "audio/webm", "ogg": "audio/ogg", "mp3": "audio/mpeg"}
DEFAULT_EXTENSION = "bin"


def _checked_id(recording_id: str) -> str:
    """Seul un UUID devient un nom de fichier : aucun chemin ne vient de l'appelant."""
    return str(uuid.UUID(recording_id))


class FileVoiceRecordingStore:
    def __init__(self, directory: Path) -> None:
        self._directory = directory

    def _find(self, recording_id: str) -> Path | None:
        return next(iter(self._directory.glob(f"{_checked_id(recording_id)}.*")), None)

    async def save(self, recording_id: str, recording: VoiceRecording) -> None:
        extension = EXTENSION_BY_MEDIA_TYPE.get(recording.media_type.split(";")[0].strip(), DEFAULT_EXTENSION)
        path = self._directory / f"{_checked_id(recording_id)}.{extension}"

        def write() -> None:
            self._directory.mkdir(parents=True, exist_ok=True)
            path.write_bytes(recording.content)

        await asyncio.to_thread(write)

    async def load(self, recording_id: str) -> VoiceRecording | None:
        path = await asyncio.to_thread(self._find, recording_id)
        if path is None:
            return None
        content = await asyncio.to_thread(path.read_bytes)
        return VoiceRecording(
            content, MEDIA_TYPE_BY_EXTENSION.get(path.suffix[1:], "application/octet-stream")
        )

    async def delete(self, recording_id: str) -> None:
        path = await asyncio.to_thread(self._find, recording_id)
        if path is not None:
            await asyncio.to_thread(path.unlink, missing_ok=True)


class InMemoryVoiceRecordingStore:
    def __init__(self) -> None:
        self.recordings_by_id: dict[str, VoiceRecording] = {}

    async def save(self, recording_id: str, recording: VoiceRecording) -> None:
        self.recordings_by_id[_checked_id(recording_id)] = recording

    async def load(self, recording_id: str) -> VoiceRecording | None:
        return self.recordings_by_id.get(_checked_id(recording_id))

    async def delete(self, recording_id: str) -> None:
        self.recordings_by_id.pop(_checked_id(recording_id), None)
