from enum import StrEnum

from pydantic import Field
from pydantic_settings import SettingsConfigDict

from hannibal_platform.settings import BaseServiceSettings


class SpeechEngineKind(StrEnum):
    WHISPER = "whisper"
    SCRIPTED = "scripted"


class AsrSettings(BaseServiceSettings):
    model_config = SettingsConfigDict(env_prefix="HX_ASR_", extra="ignore", frozen=True)

    service_name: str = "asr"
    engine: SpeechEngineKind = Field(
        default=SpeechEngineKind.WHISPER,
        description="`scripted` : renvoie `scripted_transcript` sans modèle (poste sans GPU, tests)",
    )
    whisper_model: str = "large-v3-turbo"
    whisper_fallback_model: str = Field(
        default="small", description="Chargé si le modèle principal ne tient pas (VRAM, GPU absent)"
    )
    device: str = "cuda"
    gpu_compute_type: str = Field(default="float16", description="`int8_float16` pour réduire la VRAM")
    cpu_compute_type: str = "int8"
    language: str = "en"
    beam_size: int = Field(default=5, ge=1)
    max_audio_bytes: int = Field(default=10 * 1024 * 1024, gt=0)
    min_audio_bytes: int = Field(default=2000, ge=0, description="En dessous : enregistrement trop court")
    scripted_transcript: str = "ALL SHIPS CORPEN 045 SPEED 12"
