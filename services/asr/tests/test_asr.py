import io
import wave

import pytest
from fastapi.testclient import TestClient

from hannibal_asr.application.ports import EngineTranscript, UnreadableAudio
from hannibal_asr.application.transcribe import DOMAIN_VOCABULARY, vocabulary_prompt
from hannibal_asr.infrastructure.scripted import ScriptedSpeechEngine
from hannibal_asr.infrastructure.wav_reading import is_wav, read_pcm16_wav_as_speech_samples
from hannibal_asr.infrastructure.whisper import WhisperEngine
from hannibal_asr.main import create_app
from hannibal_asr.socle.settings import AsrSettings, SpeechEngineKind

TOKEN = "jeton-interne-de-test"


def silent_wav(seconds: float = 1.0, rate: int = 16_000) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as recording:
        recording.setnchannels(1)
        recording.setsampwidth(2)
        recording.setframerate(rate)
        recording.writeframes(b"\x00\x00" * int(seconds * rate))
    return buffer.getvalue()


class RecordingEngine:
    """Garde le dernier vocabulaire reçu ; refuse l'audio qui n'est pas un WAV."""

    model_name = "test"

    def __init__(self) -> None:
        self.prompts: list[str] = []

    def transcribe(self, audio: bytes, vocabulary_prompt: str) -> EngineTranscript:
        if not audio.startswith(b"RIFF"):
            raise UnreadableAudio("pas un WAV")
        self.prompts.append(vocabulary_prompt)
        return EngineTranscript(text="ALFA TURN 30 STBD", words=[], audio_seconds=1.0)


def make_client(engine: object, *, token: str | None = None) -> TestClient:
    settings = AsrSettings(engine=SpeechEngineKind.SCRIPTED, internal_token=token)  # type: ignore[call-arg]
    return TestClient(create_app(settings, engine=engine))  # type: ignore[arg-type]


def test_vocabulary_prompt_appends_mission_ships() -> None:
    assert vocabulary_prompt([]) == DOMAIN_VOCABULARY
    assert vocabulary_prompt(["alfa", " charlie ", ""]).endswith("Alfa, Charlie.")


def test_transcribe_passes_ship_names_to_the_engine() -> None:
    engine = RecordingEngine()
    response = make_client(engine).post(
        "/transcribe?ship=alfa&ship=charlie", content=silent_wav(), headers={"Content-Type": "audio/wav"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["text"] == "ALFA TURN 30 STBD"
    assert body["model"] == "test"
    assert body["transcription_seconds"] >= 0
    assert engine.prompts[0].endswith("Alfa, Charlie.")


@pytest.mark.parametrize("audio", [b"", b"RIFF" + b"\x00" * 10, b"x" * 5000])
def test_unusable_recording_is_a_422(audio: bytes) -> None:
    response = make_client(RecordingEngine()).post("/transcribe", content=audio)
    assert response.status_code == 422
    assert response.json()["code"] == "recording_rejected"


def test_internal_token_is_required_when_configured() -> None:
    client = make_client(RecordingEngine(), token=TOKEN)
    assert client.post("/transcribe", content=silent_wav()).status_code == 401
    accepted = client.post("/transcribe", content=silent_wav(), headers={"X-Internal-Token": TOKEN})
    assert accepted.status_code == 200


def test_scripted_engine_reads_wav_duration() -> None:
    result = ScriptedSpeechEngine("ALL SHIPS SPEED 12").transcribe(silent_wav(2.0), "")
    assert result.audio_seconds == 2.0
    assert [word.text for word in result.words] == ["ALL", "SHIPS", "SPEED", "12"]


def pcm16_wav(frames: list[tuple[int, ...]], rate: int) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as recording:
        recording.setnchannels(len(frames[0]))
        recording.setsampwidth(2)
        recording.setframerate(rate)
        recording.writeframes(
            b"".join(value.to_bytes(2, "little", signed=True) for frame in frames for value in frame)
        )
    return buffer.getvalue()


def test_wav_reader_mixes_stereo_to_mono_without_pyav() -> None:
    audio = pcm16_wav([(16384, 0), (-16384, -16384)], 16_000)
    assert is_wav(audio)
    assert read_pcm16_wav_as_speech_samples(audio, 16_000) == [0.25, -0.5]


def test_wav_reader_resamples_to_speech_rate() -> None:
    samples = read_pcm16_wav_as_speech_samples(pcm16_wav([(0,)] * 4800, 48_000), 16_000)
    assert len(samples) == 1600


def test_wav_reader_refuses_8_bit_wav() -> None:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as recording:
        recording.setnchannels(1)
        recording.setsampwidth(1)
        recording.setframerate(8000)
        recording.writeframes(b"\x80" * 8000)
    with pytest.raises(wave.Error):
        read_pcm16_wav_as_speech_samples(buffer.getvalue(), 16_000)
    assert not is_wav(b"OggS" + b"\x00" * 20)


def test_whisper_engine_falls_back_from_gpu_to_cpu() -> None:
    engine = WhisperEngine(
        model="large-v3-turbo",
        fallback_model="small",
        device="cuda",
        gpu_compute_type="float16",
        cpu_compute_type="int8",
        language="en",
        beam_size=5,
    )
    assert engine._attempts == [
        ("large-v3-turbo", "cuda", "float16"),
        ("small", "cuda", "float16"),
        ("small", "cpu", "int8"),
    ]
