from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request

from hannibal_asr.application.transcribe import RecordingRejected, TranscribeRecording
from hannibal_contracts.asr import TranscribedWord, Transcription
from hannibal_platform.errors import HannibalError
from hannibal_platform.internal_auth import require_internal_token
from hannibal_platform.settings import BaseServiceSettings


class UnusableRecording(HannibalError):
    status = HTTPStatus.UNPROCESSABLE_ENTITY
    code = "recording_rejected"
    message = "Enregistrement inutilisable : trop court, trop long ou format inconnu."


def transcription_router(transcribe: TranscribeRecording, settings: BaseServiceSettings) -> APIRouter:
    router = APIRouter(dependencies=[Depends(require_internal_token(settings))])

    @router.post(
        "/transcribe",
        response_model=Transcription,
        openapi_extra={"requestBody": {"content": {"audio/wav": {}, "application/octet-stream": {}}}},
    )
    async def transcribe_recording(
        request: Request,
        ship: Annotated[list[str] | None, Query(description="Indicatifs ajoutés au vocabulaire")] = None,
    ) -> Transcription:
        audio = await request.body()
        try:
            result = await transcribe(audio, ship or [])
        except RecordingRejected as error:
            raise UnusableRecording(str(error)) from error
        return Transcription(
            text=result.transcript.text,
            words=[
                TranscribedWord(
                    word=word.text, probability=word.probability, start_s=word.start_s, end_s=word.end_s
                )
                for word in result.transcript.words
            ],
            audio_seconds=result.transcript.audio_seconds,
            transcription_seconds=result.transcription_seconds,
            model=result.model,
        )

    return router
