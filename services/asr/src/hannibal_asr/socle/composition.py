from hannibal_asr.application.ports import SpeechEngine
from hannibal_asr.application.transcribe import TranscribeRecording
from hannibal_asr.infrastructure.scripted import ScriptedSpeechEngine
from hannibal_asr.infrastructure.whisper import WhisperEngine
from hannibal_asr.socle.settings import AsrSettings, SpeechEngineKind


def build_speech_engine(settings: AsrSettings) -> SpeechEngine:
    if settings.engine is SpeechEngineKind.SCRIPTED:
        return ScriptedSpeechEngine(settings.scripted_transcript)
    return WhisperEngine(
        model=settings.whisper_model,
        fallback_model=settings.whisper_fallback_model,
        device=settings.device,
        gpu_compute_type=settings.gpu_compute_type,
        cpu_compute_type=settings.cpu_compute_type,
        language=settings.language,
        beam_size=settings.beam_size,
    )


def build_transcribe_recording(settings: AsrSettings, engine: SpeechEngine) -> TranscribeRecording:
    return TranscribeRecording(
        engine, min_audio_bytes=settings.min_audio_bytes, max_audio_bytes=settings.max_audio_bytes
    )
