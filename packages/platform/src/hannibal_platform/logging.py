"""Journal technique : une ligne JSON par événement, sur stdout.

Champs toujours présents : ts, level, service, request_id, event.
Interdit dans le journal : mot de passe, cookie, jeton, audio, texte de publication, prompt complet.
"""

import logging
import sys
from typing import Any

import structlog
from structlog.typing import EventDict, WrappedLogger

from hannibal_platform.context import current_request_id

_REDACTED_KEYS = frozenset({"password", "token", "cookie", "authorization", "internal_token", "secret"})


def _add_request_id(_: WrappedLogger, __: str, event_dict: EventDict) -> EventDict:
    event_dict.setdefault("request_id", current_request_id())
    return event_dict


def _redact(_: WrappedLogger, __: str, event_dict: EventDict) -> EventDict:
    for key in event_dict.keys() & _REDACTED_KEYS:
        event_dict[key] = "***"
    return event_dict


def configure_logging(service: str, level: str = "INFO", *, json: bool = True) -> None:
    numeric_level = logging.getLevelNamesMapping().get(level.upper(), logging.INFO)

    def _add_service(_: WrappedLogger, __: str, event_dict: EventDict) -> EventDict:
        event_dict.setdefault("service", service)
        return event_dict

    processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True, key="ts"),
        _add_service,
        _add_request_id,
        _redact,
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer() if json else structlog.dev.ConsoleRenderer(),
    ]
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(numeric_level),
        logger_factory=lambda *_: structlog.PrintLogger(sys.stdout),
        cache_logger_on_first_use=False,
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    logger: structlog.stdlib.BoundLogger = structlog.get_logger(name)
    return logger
