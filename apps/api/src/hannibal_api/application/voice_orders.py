"""Handler `SubmitVoice` (§ 7) : l'enregistrement est gardé, transcrit, puis suit le circuit de `SubmitOrder`.

L'identifiant de l'enregistrement devient celui de la commande : le registre retrouve l'audio par commande.
Un ordre entendu mais non reconnu reste au registre (`transcribed` avec le motif du refus), avec son audio.
"""

import uuid
from dataclasses import dataclass
from typing import Any

from hannibal_api.application.commands import Commands
from hannibal_api.application.gpu_gate import GpuGate
from hannibal_api.application.missions import Missions, NotFound, Unprocessable
from hannibal_api.application.ports import (
    MissionJournal,
    RecordingUnusable,
    SpeechTranscriber,
    VoiceRecordingStore,
)
from hannibal_api.domain.audit import AuditEntry, AuditEvent
from hannibal_api.domain.commands import Command, CommandSource
from hannibal_api.domain.voice import VoiceRecording, VoiceTranscript
from hannibal_platform.logging import get_logger

log = get_logger(__name__)


class RecordingRejected(Unprocessable):
    code = "recording_rejected"
    message = "Enregistrement inutilisable : trop court, trop long ou format inconnu."


class RecordingNotFound(NotFound):
    code = "recording_not_found"
    message = "Aucun enregistrement pour cette commande."


@dataclass(frozen=True, slots=True)
class VoiceOrderResult:
    recording_id: str
    transcript: VoiceTranscript
    interpretation: dict[str, Any]
    command: Command | None


class VoiceOrders:
    def __init__(
        self,
        missions: Missions,
        commands: Commands,
        transcriber: SpeechTranscriber,
        recordings: VoiceRecordingStore,
        journal: MissionJournal,
        gate: GpuGate,
        *,
        min_recording_bytes: int,
        max_recording_bytes: int,
    ) -> None:
        self._missions = missions
        self._commands = commands
        self._transcriber = transcriber
        self._recordings = recordings
        self._journal = journal
        self._gate = gate
        self._min_recording_bytes = min_recording_bytes
        self._max_recording_bytes = max_recording_bytes

    async def submit(
        self, mission_id: str, recording: VoiceRecording, *, actor_id: str, parent_id: str | None
    ) -> VoiceOrderResult:
        if not self._min_recording_bytes <= len(recording.content) <= self._max_recording_bytes:
            raise RecordingRejected(size_bytes=len(recording.content))
        ship_names = self._missions.ship_names(mission_id)
        recording_id = str(uuid.uuid4())
        await self._recordings.save(recording_id, recording)
        try:
            async with self._gate.voice():
                transcript = await self._transcriber.transcribe(recording, ship_names)
            transcribed = AuditEntry(
                AuditEvent.TRANSCRIBED,
                actor_id,
                mission_id,
                {**transcript.audit_payload(), "parent_id": parent_id},
                command_id=recording_id,
            )
            interpretation, command = await self._commands.submit_for_review(
                mission_id,
                transcript.text,
                actor_id=actor_id,
                parent_id=parent_id,
                source=CommandSource.VOICE,
                command_id=recording_id,
                preceding_entries=[transcribed],
            )
            if command is None:
                await self._journal.record(
                    AuditEntry(
                        AuditEvent.TRANSCRIBED,
                        actor_id,
                        mission_id,
                        {**transcribed.payload, "refusal_reason": interpretation.get("error")},
                        command_id=recording_id,
                    )
                )
        except RecordingUnusable as error:
            await self._recordings.delete(recording_id)
            raise RecordingRejected(recording_id=recording_id) from error
        except BaseException:
            await self._recordings.delete(recording_id)
            raise
        log.info(
            "voice_order_submitted",
            recording_id=recording_id,
            recognized=command is not None,
            transcription_seconds=transcript.transcription_seconds,
        )
        return VoiceOrderResult(recording_id, transcript, interpretation, command)

    async def read_recording(self, recording_id: str) -> VoiceRecording:
        recording = await self._recordings.load(recording_id)
        if recording is None:
            raise RecordingNotFound(recording_id=recording_id)
        return recording
