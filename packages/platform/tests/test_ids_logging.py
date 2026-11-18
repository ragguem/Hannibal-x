import json

import pytest

from hannibal_platform.context import request_id_var
from hannibal_platform.ids import uuid7
from hannibal_platform.logging import configure_logging, get_logger


def test_uuid7_version_variant_and_order() -> None:
    ids = [uuid7() for _ in range(200)]
    assert all(i.version == 7 for i in ids)
    assert all(i.variant == "specified in RFC 4122" for i in ids)
    timestamps = [i.int >> 80 for i in ids]
    assert timestamps == sorted(timestamps)
    assert len(set(ids)) == len(ids)


def test_log_line_is_json_with_required_fields(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging("svc", "INFO", json=True)
    token = request_id_var.set("req-12345678")
    try:
        get_logger("t").info("something_happened", password="hunter2", count=3)
    finally:
        request_id_var.reset(token)
    line = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert line["event"] == "something_happened"
    assert line["service"] == "svc"
    assert line["level"] == "info"
    assert line["request_id"] == "req-12345678"
    assert "ts" in line
    assert line["password"] == "***"
    assert line["count"] == 3


def test_level_filtering(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging("svc", "WARNING", json=True)
    get_logger("t").info("hidden")
    assert "hidden" not in capsys.readouterr().out
