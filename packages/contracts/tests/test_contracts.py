import pytest
from pydantic import ValidationError

from hannibal_contracts.common import ErrorBody, Health
from hannibal_contracts.export import SCHEMAS_DIR, expected_files


def test_unknown_field_is_refused() -> None:
    with pytest.raises(ValidationError):
        Health.model_validate({"status": "ok", "service": "api", "version": "0.1.0", "extra": 1})


def test_models_are_frozen() -> None:
    body = ErrorBody(code="internal", message="Erreur interne.", request_id=None)
    with pytest.raises(ValidationError):
        body.code = "other"  # type: ignore[misc]


def test_published_schemas_match_models() -> None:
    expected = expected_files()
    published = {p.name: p.read_text(encoding="utf-8") for p in SCHEMAS_DIR.glob("*.json")}
    assert published.keys() == expected.keys(), "uv run hx-export-schemas"
    for name, content in expected.items():
        assert published[name] == content, f"{name} a dérivé : uv run hx-export-schemas"
