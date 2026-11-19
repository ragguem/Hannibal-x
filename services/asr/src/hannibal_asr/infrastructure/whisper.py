"""Adaptateur faster-whisper de `SpeechEngine` (repris de legacy/hx/scripts/hx_service.py)."""

import io
from typing import Any

from hannibal_asr.application.ports import EngineTranscript, HeardWord, UnreadableAudio
from hannibal_platform.logging import get_logger

log = get_logger(__name__)

SAMPLE_RATE = 16_000


class WhisperEngine:
    """Charge le premier modèle qui tient : principal sur GPU, repli sur GPU, puis repli sur processeur."""

    def __init__(
        self,
        *,
        model: str,
        fallback_model: str,
        device: str,
        gpu_compute_type: str,
        cpu_compute_type: str,
        language: str,
        beam_size: int,
    ) -> None:
        self._attempts = [(model, device, gpu_compute_type if device != "cpu" else cpu_compute_type)]
        if fallback_model != model:
            self._attempts.append(
                (fallback_model, device, gpu_compute_type if device != "cpu" else cpu_compute_type)
            )
        if device != "cpu":
            self._attempts.append((fallback_model, "cpu", cpu_compute_type))
        self._language = language
        self._beam_size = beam_size
        self._model: Any = None
        self._model_name = model

    @property
    def model_name(self) -> str:
        return self._model_name

    def load(self) -> None:
        from faster_whisper import WhisperModel

        for name, device, compute_type in self._attempts:
            try:
                self._model = WhisperModel(name, device=device, compute_type=compute_type)
            except (RuntimeError, ValueError, OSError) as error:
                log.warning("whisper_load_failed", model=name, device=device, error=str(error))
                continue
            self._model_name = f"{name}@{device}"
            log.info("whisper_loaded", model=name, device=device, compute_type=compute_type)
            return
        raise RuntimeError("aucun modèle Whisper n'a pu être chargé")

    def transcribe(self, audio: bytes, vocabulary_prompt: str) -> EngineTranscript:
        from faster_whisper.audio import decode_audio

        if self._model is None:
            self.load()
        try:
            samples = decode_audio(io.BytesIO(audio), sampling_rate=SAMPLE_RATE)
        except Exception as error:  # PyAV lève des erreurs propres à chaque format
            raise UnreadableAudio(type(error).__name__) from error
        segments, _ = self._model.transcribe(
            samples,
            language=self._language,
            beam_size=self._beam_size,
            word_timestamps=True,
            initial_prompt=vocabulary_prompt,
            condition_on_previous_text=False,
            vad_filter=False,
        )
        segments = list(segments)
        words = [
            HeardWord(
                text=word.word.strip(),
                probability=round(float(word.probability), 3),
                start_s=round(float(word.start), 2),
                end_s=round(float(word.end), 2),
            )
            for segment in segments
            for word in (segment.words or [])
        ]
        return EngineTranscript(
            text=" ".join(segment.text.strip() for segment in segments).strip(),
            words=words,
            audio_seconds=round(len(samples) / SAMPLE_RATE, 2),
        )
