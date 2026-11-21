"""`SubmitVoice` et lecture de l'audio au registre, en mode `fake` (transcripteur scripté)."""

import asyncio
import io
import wave
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient
from mission_snapshot import run_body, run_path

from hannibal_api.application.ports import RecordingUnusable
from hannibal_api.domain.voice import VoiceRecording
from hannibal_api.infrastructure.asr import AsrClient, ScriptedTranscriber
from hannibal_api.infrastructure.recordings import FileVoiceRecordingStore, InMemoryVoiceRecordingStore
from hannibal_api.socle.container import Container
from hannibal_api.socle.main import create_app
from hannibal_api.socle.settings import AdapterMode, ApiSettings
from hannibal_platform.errors import DependencyUnavailable

RUNNER_PERIOD_S = 0.5
HEARD_ORDER = "ALL SHIPS TURN 30 STBD"


def spoken_wav(seconds: float = 1.0) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as recording:
        recording.setnchannels(1)
        recording.setsampwidth(2)
        recording.setframerate(16_000)
        recording.writeframes(b"\x01\x00" * int(seconds * 16_000))
    return buffer.getvalue()


class ManualClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


class VoiceHarness:
    def __init__(self) -> None:
        settings = ApiSettings(
            adapters=AdapterMode.FAKE, log_json=True, mission_runner_period_s=0, dispatch_poll_period_s=0
        )  # type: ignore[call-arg]
        self.clock = ManualClock()
        container = Container(settings=settings)
        container.clock.override(self.clock)
        self.client = TestClient(create_app(settings, container), raise_server_exceptions=False)
        self.missions = container.missions()
        self.transcriber: ScriptedTranscriber = container.transcriber()
        self.recordings: InMemoryVoiceRecordingStore = container.recordings()

    def start_mission(self) -> str:
        response = self.client.put(run_path(), json=run_body())
        mission_id = str(response.json()["id"])
        for _ in range(int(40 / RUNNER_PERIOD_S)):
            self.clock.now += RUNNER_PERIOD_S
            asyncio.run(self.missions.advance(mission_id))
        return mission_id

    def speak(self, mission_id: str, heard: str, audio: bytes | None = None, **form: str) -> httpx.Response:
        self.transcriber.queue.append(heard)
        return self.client.post(
            f"/v1/missions/{mission_id}/voice",
            files={"audio": ("ordre.wav", audio if audio is not None else spoken_wav(), "audio/wav")},
            data=form,
            headers={"X-Hx-User": "alice"},
        )

    def audit_events(self, mission_id: str) -> list[dict[str, Any]]:
        return list(self.client.get("/v1/audit", params={"mission_id": mission_id}).json()["events"])


@pytest.fixture
def harness() -> VoiceHarness:
    return VoiceHarness()


def test_heard_order_becomes_a_voice_command_awaiting_review(harness: VoiceHarness) -> None:
    mission_id = harness.start_mission()
    response = harness.speak(mission_id, HEARD_ORDER)
    assert response.status_code == 200, response.text
    outcome = response.json()
    assert outcome["accepted"] is True
    assert outcome["transcript"] == HEARD_ORDER
    assert outcome["command_state"] == "awaiting_review"
    assert outcome["command_id"] == outcome["recording_id"]
    assert [word["word"] for word in outcome["heard_words"]][:2] == ["ALL", "SHIPS"]

    command = harness.client.get(f"/v1/commands/{outcome['command_id']}").json()
    assert command["source"] == "voice"
    assert command["submitted_by"] == "alice"

    trail = [e for e in harness.audit_events(mission_id) if e["command_id"] == outcome["command_id"]]
    assert [e["event"] for e in trail] == ["transcribed", "awaiting_review"]
    assert trail[0]["payload"]["transcript"] == HEARD_ORDER
    assert trail[0]["payload"]["asr_model"] == "scripted"


def test_recording_is_served_back_to_the_register(harness: VoiceHarness) -> None:
    mission_id = harness.start_mission()
    audio = spoken_wav()
    outcome = harness.speak(mission_id, HEARD_ORDER, audio).json()
    served = harness.client.get(f"/v1/audit/{outcome['recording_id']}/audio")
    assert served.status_code == 200
    assert served.headers["content-type"] == "audio/wav"
    assert served.content == audio
    missing = harness.client.get("/v1/audit/00000000-0000-4000-8000-000000000000/audio")
    assert missing.status_code == 404
    assert missing.json()["code"] == "recording_not_found"


def test_unrecognized_speech_is_kept_in_the_register_without_command(harness: VoiceHarness) -> None:
    mission_id = harness.start_mission()
    outcome = harness.speak(mission_id, "GOOD MORNING EVERYONE").json()
    assert outcome["accepted"] is False
    assert outcome["refusal_reason"]
    assert outcome["command_id"] is None
    trail = [e for e in harness.audit_events(mission_id) if e["command_id"] == outcome["recording_id"]]
    assert [e["event"] for e in trail] == ["transcribed"]
    assert trail[0]["payload"]["refusal_reason"] == outcome["refusal_reason"]
    assert harness.client.get(f"/v1/audit/{outcome['recording_id']}/audio").status_code == 200


def test_correction_is_chained_to_the_corrected_command(harness: VoiceHarness) -> None:
    mission_id = harness.start_mission()
    first = harness.speak(mission_id, HEARD_ORDER).json()
    correction = harness.speak(mission_id, "ALL SHIPS TURN 40 STBD", parent_id=first["command_id"]).json()
    command = harness.client.get(f"/v1/commands/{correction['command_id']}").json()
    assert command["parent_id"] == first["command_id"]


def test_too_short_recording_is_refused_and_not_kept(harness: VoiceHarness) -> None:
    mission_id = harness.start_mission()
    response = harness.speak(mission_id, HEARD_ORDER, audio=b"RIFF")
    assert response.status_code == 422
    assert response.json()["code"] == "recording_rejected"
    assert harness.recordings.recordings_by_id == {}


def test_voice_order_after_the_mission_is_refused(harness: VoiceHarness) -> None:
    mission_id = harness.start_mission()
    harness.client.delete(f"/v1/missions/{mission_id}")
    response = harness.speak(mission_id, HEARD_ORDER)
    assert response.status_code == 409
    assert harness.recordings.recordings_by_id == {}


def asr_transport(status: int, body: dict[str, Any] | str) -> httpx.MockTransport:
    seen: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if isinstance(body, str):
            return httpx.Response(status, text=body)
        return httpx.Response(status, json=body)

    transport = httpx.MockTransport(handle)
    transport.seen = seen  # type: ignore[attr-defined]
    return transport


async def test_asr_client_sends_ship_names_and_maps_the_transcription() -> None:
    transport = asr_transport(
        200,
        {
            "text": "ALFA TURN 30 STBD",
            "words": [{"word": "ALFA", "probability": 0.9, "start_s": 0.0, "end_s": 0.4}],
            "audio_seconds": 1.2,
            "transcription_seconds": 0.3,
            "model": "large-v3-turbo@cuda",
        },
    )
    client = AsrClient("http://asr", token="t", timeout_s=1, transport=transport)
    transcript = await client.transcribe(VoiceRecording(b"RIFF", "audio/wav"), ["alfa", "charlie"])
    request = transport.seen[0]  # type: ignore[attr-defined]
    assert request.url.params.get_list("ship") == ["alfa", "charlie"]
    assert request.headers["content-type"] == "audio/wav"
    assert transcript.text == "ALFA TURN 30 STBD"
    assert transcript.words[0].confidence == 0.9
    assert transcript.model == "large-v3-turbo@cuda"


async def test_asr_client_distinguishes_unusable_audio_from_outage() -> None:
    refused = AsrClient("http://asr", token=None, timeout_s=1, transport=asr_transport(422, "court"))
    with pytest.raises(RecordingUnusable):
        await refused.transcribe(VoiceRecording(b"x", "audio/wav"), [])
    broken = AsrClient("http://asr", token=None, timeout_s=1, transport=asr_transport(503, "panne"))
    with pytest.raises(DependencyUnavailable):
        await broken.transcribe(VoiceRecording(b"x", "audio/wav"), [])


async def test_file_store_keeps_one_file_per_command(tmp_path: Path) -> None:
    store = FileVoiceRecordingStore(tmp_path / "recordings")
    recording_id = "11111111-1111-4111-8111-111111111111"
    await store.save(recording_id, VoiceRecording(b"RIFFdata", "audio/wav"))
    assert (tmp_path / "recordings" / f"{recording_id}.wav").read_bytes() == b"RIFFdata"
    loaded = await store.load(recording_id)
    assert loaded == VoiceRecording(b"RIFFdata", "audio/wav")
    await store.delete(recording_id)
    assert await store.load(recording_id) is None
    with pytest.raises(ValueError, match="badly formed"):
        await store.load("../../etc/passwd")
