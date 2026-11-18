from fastapi import Depends
from fastapi.testclient import TestClient
from pydantic import BaseModel, SecretStr

from hannibal_platform.app import create_service_app
from hannibal_platform.context import current_request_id
from hannibal_platform.errors import Conflict, DependencyUnavailable
from hannibal_platform.internal_auth import require_internal_token
from hannibal_platform.settings import BaseServiceSettings, Environment


class Payload(BaseModel):
    value: int


def make_app(**overrides: object) -> TestClient:
    settings = BaseServiceSettings(service_name="test-svc", log_json=True, **overrides)  # type: ignore[arg-type]
    app = create_service_app(settings, version="0.1.0", title="test")

    @app.get("/conflict")
    async def conflict() -> None:
        raise Conflict("détail interne")

    @app.get("/dependency")
    async def dependency() -> None:
        raise DependencyUnavailable("ollama", "injoignable")

    @app.get("/crash")
    async def crash() -> None:
        raise RuntimeError("secret interne")

    @app.post("/payload")
    async def payload(body: Payload) -> Payload:
        return body

    @app.get("/request-id")
    async def request_id() -> dict[str, str | None]:
        return {"request_id": current_request_id()}

    @app.get("/internal", dependencies=[Depends(require_internal_token(settings))])
    async def internal() -> dict[str, bool]:
        return {"ok": True}

    return TestClient(app, raise_server_exceptions=False)


def test_health() -> None:
    response = make_app().get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "test-svc", "version": "0.1.0"}


def test_request_id_is_propagated() -> None:
    response = make_app().get("/request-id", headers={"X-Request-Id": "abcdef12-3456"})
    assert response.headers["x-request-id"] == "abcdef12-3456"
    assert response.json() == {"request_id": "abcdef12-3456"}


def test_request_id_is_generated_when_invalid() -> None:
    response = make_app().get("/request-id", headers={"X-Request-Id": "bad id!"})
    generated = response.headers["x-request-id"]
    assert generated != "bad id!"
    assert response.json() == {"request_id": generated}


def test_hannibal_error_is_translated_without_detail() -> None:
    response = make_app().get("/conflict")
    assert response.status_code == 409
    body = response.json()
    assert body["code"] == "conflict"
    assert "détail interne" not in body["message"]
    assert body["request_id"] == response.headers["x-request-id"]


def test_dependency_unavailable_names_dependency() -> None:
    response = make_app().get("/dependency")
    assert response.status_code == 503
    assert response.json()["dependency"] == "ollama"


def test_unexpected_error_is_internal_and_hides_message() -> None:
    response = make_app().get("/crash")
    assert response.status_code == 500
    assert response.json()["code"] == "internal"
    assert "secret" not in response.text


def test_validation_error() -> None:
    response = make_app().post("/payload", json={"value": "abc"})
    assert response.status_code == 422
    assert response.json()["code"] == "invalid_request"


def test_unknown_route() -> None:
    response = make_app().get("/nope")
    assert response.status_code == 404
    assert response.json()["code"] == "not_found"


def test_internal_token_open_in_dev_without_token() -> None:
    assert make_app().get("/internal").status_code == 200


def test_internal_token_required_when_configured() -> None:
    client = make_app(internal_token=SecretStr("s3cret"))
    assert client.get("/internal").status_code == 401
    assert client.get("/internal", headers={"X-Internal-Token": "wrong"}).status_code == 403
    assert client.get("/internal", headers={"X-Internal-Token": "s3cret"}).status_code == 200


def test_internal_token_mandatory_in_production() -> None:
    client = make_app(environment=Environment.PRODUCTION)
    assert client.get("/internal").status_code == 403


def test_metrics_open_locally_and_counts_route_templates() -> None:
    client = make_app()
    client.get("/health")
    body = client.get("/metrics").text
    assert 'http_requests_total{code="200",method="GET",route="/health"}' in body


def test_metrics_protected_by_token() -> None:
    client = make_app(metrics_token=SecretStr("collect"))
    assert client.get("/metrics").status_code == 401
    assert client.get("/metrics", headers={"Authorization": "Bearer nope"}).status_code == 403
    assert client.get("/metrics", headers={"Authorization": "Bearer collect"}).status_code == 200


def test_metrics_closed_in_production_without_token() -> None:
    assert make_app(environment=Environment.PRODUCTION).get("/metrics").status_code == 403
