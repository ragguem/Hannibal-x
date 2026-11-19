import asyncio

from fastapi.testclient import TestClient

from hannibal_api.application.check_readiness import CheckReadiness
from hannibal_api.domain.readiness import OverallState, ProbeResult, ProbeState
from hannibal_api.infrastructure.probes import FakeProbe, HttpProbe, PostgresProbe
from hannibal_api.socle.main import create_app
from hannibal_api.socle.settings import AdapterMode, ApiSettings


def client(**overrides: object) -> TestClient:
    settings = ApiSettings(**{"adapters": AdapterMode.FAKE, "log_json": True, **overrides})  # type: ignore[arg-type]
    return TestClient(create_app(settings), raise_server_exceptions=False)


def test_health() -> None:
    response = client().get("/v1/health")
    assert response.status_code == 200
    assert response.json()["service"] == "api"


def test_ready_with_fake_adapters() -> None:
    response = client().get("/v1/ready")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert {d["name"]: d["state"] for d in body["dependencies"]} == {
        "postgres": "up",
        "ollama": "disabled",
        "sim-bridge": "up",
        "asr": "up",
    }


def test_ready_degraded_when_database_missing_in_real_mode() -> None:
    response = client(adapters=AdapterMode.REAL).get("/v1/ready")
    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "degraded"
    assert {d["name"]: d["state"] for d in body["dependencies"]} == {
        "postgres": "down",
        "ollama": "disabled",
        "sim-bridge": "disabled",
        "asr": "disabled",
    }


def test_openapi_is_published() -> None:
    paths = client().get("/v1/openapi.json").json()["paths"]
    assert {"/v1/health", "/v1/ready"} <= paths.keys()


class SlowProbe:
    name = "slow"
    required = True

    async def check(self) -> ProbeResult:
        await asyncio.sleep(5)
        return ProbeResult(self.name, ProbeState.UP, self.required)


async def test_slow_probe_counts_as_down() -> None:
    report = await CheckReadiness([SlowProbe(), FakeProbe("db")], timeout_s=0.05)()
    assert report.state is OverallState.DEGRADED
    assert report.dependencies[0].reason == "timeout"


async def test_optional_dependency_down_does_not_block() -> None:
    probes = [FakeProbe("db"), FakeProbe("ollama", ProbeState.DOWN, required=False)]
    assert (await CheckReadiness(probes, timeout_s=1)()).state is OverallState.READY


async def test_postgres_probe_unreachable() -> None:
    result = await PostgresProbe("postgresql://hx:hx@127.0.0.1:1/hx", timeout_s=0.5).check()
    assert result.state is ProbeState.DOWN


async def test_http_probe_unreachable() -> None:
    result = await HttpProbe("ollama", "http://127.0.0.1:1/api/version", timeout_s=0.5).check()
    assert result.state is ProbeState.DOWN
