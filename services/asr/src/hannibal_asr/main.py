"""Lancement : `uvicorn --factory hannibal_asr.main:create_app`."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from hannibal_asr import __version__
from hannibal_asr.application.ports import SpeechEngine
from hannibal_asr.infrastructure.whisper import WhisperEngine
from hannibal_asr.presentation.http import transcription_router
from hannibal_asr.socle.composition import build_speech_engine, build_transcribe_recording
from hannibal_asr.socle.settings import AsrSettings
from hannibal_platform.app import create_service_app


def create_app(settings: AsrSettings | None = None, engine: SpeechEngine | None = None) -> FastAPI:
    settings = settings or AsrSettings()
    engine = engine or build_speech_engine(settings)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        if isinstance(engine, WhisperEngine):
            await asyncio.to_thread(engine.load)
        yield

    app = create_service_app(
        settings,
        version=__version__,
        title="Hannibal X asr",
        lifespan=lifespan,
        docs_url="/docs" if settings.is_local else None,
        redoc_url=None,
    )
    app.include_router(transcription_router(build_transcribe_recording(settings, engine), settings))
    return app
