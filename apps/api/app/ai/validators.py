import json
import re
from typing import Any

from app.ai.errors import AIInvalidOutput

_FENCE_RE = re.compile(r"^```(?:json)?\s*\n(?P<body>.*)\n```$", re.DOTALL | re.IGNORECASE)


def parse_json_output(text: str) -> Any:
    """JSON estricto. Solo se tolera una cerca de markdown (```json … ```) que envuelva todo el texto."""
    stripped = text.strip()
    match = _FENCE_RE.match(stripped)
    if match:
        stripped = match.group("body").strip()
    try:
        return json.loads(stripped)
    except (json.JSONDecodeError, ValueError) as exc:
        raise AIInvalidOutput("json_malformado") from exc
