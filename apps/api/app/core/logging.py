import json
import logging
import re
import sys
from datetime import UTC, datetime
from typing import Any

# Atributos estándar de LogRecord que no se emiten como campos estructurados.
_RESERVED = set(vars(logging.makeLogRecord({}))) | {"message", "asctime"}

# Defensa en profundidad: aunque el código no registre PII, se enmascaran correos,
# tokens en URLs y hashes Argon2 si llegaran a colarse en un mensaje.
_EMAIL_RE = re.compile(r"[^@\s\"']+@[^@\s\"']+")
_TOKEN_RE = re.compile(r"(token=)[^&\s\"']+", re.IGNORECASE)
_ARGON_RE = re.compile(r"\$argon2[^\s\"']+")
_SENSITIVE_KEYS = {"email", "password", "password_hash", "token", "token_hash", "session_token"}


def redact(value: str) -> str:
    value = _TOKEN_RE.sub(r"\1[REDACTED]", value)
    value = _ARGON_RE.sub("[REDACTED]", value)
    return _EMAIL_RE.sub("[REDACTED_EMAIL]", value)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "event": redact(record.getMessage()),
        }
        for key, value in vars(record).items():
            if key in _RESERVED or key.startswith("_"):
                continue
            if key in _SENSITIVE_KEYS:
                payload[key] = "[REDACTED]"
            else:
                payload[key] = redact(value) if isinstance(value, str) else value
        if record.exc_info:
            payload["exc_type"] = record.exc_info[0].__name__ if record.exc_info[0] else None
        return json.dumps(payload, default=str, ensure_ascii=False)


def configure_logging(level: int = logging.INFO) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger("fitia")
    root.handlers = [handler]
    root.setLevel(level)
    root.propagate = False
