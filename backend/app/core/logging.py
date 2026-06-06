import json
import logging
from contextvars import ContextVar, Token
from datetime import datetime, timezone


_REQUEST_ID_CONTEXT: ContextVar[str] = ContextVar("request_id", default="")
LOGGER_NAME = "brainchain"


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "event": getattr(record, "event", record.getMessage()),
            "request_id": getattr(record, "request_id", get_request_id()),
            "path": getattr(record, "path", ""),
            "method": getattr(record, "method", ""),
            "status_code": getattr(record, "status_code", 0),
        }
        return json.dumps(payload, ensure_ascii=True)


def configure_logging(log_level: str) -> logging.Logger:
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(log_level.upper())
    logger.propagate = False

    if not any(getattr(handler, "_brainchain_json_handler", False) for handler in logger.handlers):
        logger.handlers.clear()
        handler = logging.StreamHandler()
        handler.setFormatter(JsonFormatter())
        handler._brainchain_json_handler = True  # type: ignore[attr-defined]
        logger.addHandler(handler)

    return logger


def get_logger(name: str = "") -> logging.Logger:
    return logging.getLogger(f"{LOGGER_NAME}.{name}" if name else LOGGER_NAME)


def set_request_id(request_id: str) -> Token[str]:
    return _REQUEST_ID_CONTEXT.set(request_id)


def reset_request_id(token: Token[str]) -> None:
    _REQUEST_ID_CONTEXT.reset(token)


def get_request_id() -> str:
    return _REQUEST_ID_CONTEXT.get()

__all__ = [name for name in globals() if not name.startswith('_')]
