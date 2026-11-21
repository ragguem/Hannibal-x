"""Lecture des WAV PCM 16 bits sans PyAV : la console envoie toujours ce format (16 kHz mono)."""

import io
import sys
import wave
from array import array

PCM16_FULL_SCALE = 32768.0


def is_wav(audio: bytes) -> bool:
    return audio[:4] == b"RIFF" and audio[8:12] == b"WAVE"


def read_pcm16_wav_as_speech_samples(audio: bytes, sampling_rate: int) -> list[float]:
    """Échantillons mono entre -1 et 1 à `sampling_rate` ; `wave.Error` si le WAV n'est pas du PCM 16 bits."""
    with wave.open(io.BytesIO(audio), "rb") as recording:
        if recording.getsampwidth() != 2:
            raise wave.Error("seul le PCM 16 bits est lu")
        channels = recording.getnchannels()
        source_rate = recording.getframerate()
        pcm = array("h")
        pcm.frombytes(recording.readframes(recording.getnframes()))
    if sys.byteorder == "big":
        pcm.byteswap()
    mono = [
        sum(pcm[index : index + channels]) / (channels * PCM16_FULL_SCALE)
        for index in range(0, len(pcm) - channels + 1, channels)
    ]
    return resample_linear(mono, source_rate, sampling_rate)


def resample_linear(samples: list[float], source_rate: int, target_rate: int) -> list[float]:
    if source_rate == target_rate or not samples:
        return samples
    target_length = max(1, round(len(samples) * target_rate / source_rate))
    step = (len(samples) - 1) / max(1, target_length - 1)
    resampled = []
    for index in range(target_length):
        position = index * step
        left = int(position)
        right = min(left + 1, len(samples) - 1)
        weight = position - left
        resampled.append(samples[left] * (1 - weight) + samples[right] * weight)
    return resampled
