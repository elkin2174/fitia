import json
import logging

from app.core.logging import JsonFormatter, redact


def test_redact_enmascara_correo_token_y_hash() -> None:
    text = redact("ana@correounivalle.edu.co abrió /verificar-correo?token=abc123 con $argon2id$v=19$m=1$x")

    assert "ana@correounivalle.edu.co" not in text
    assert "abc123" not in text
    assert "$argon2id$" not in text


def test_formatter_emite_json_y_oculta_campos_sensibles() -> None:
    record = logging.makeLogRecord(
        {"name": "fitia.test", "levelname": "INFO", "msg": "user_registered", "user_id": "u1", "email": "a@b.co"}
    )

    payload = json.loads(JsonFormatter().format(record))

    assert payload["event"] == "user_registered"
    assert payload["user_id"] == "u1"
    assert payload["email"] == "[REDACTED]"
