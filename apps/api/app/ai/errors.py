from typing import Literal

ProviderErrorKind = Literal["timeout", "rate_limited", "server_error", "client_error", "network"]

# Estado de la llamada tal como se registra en ai_call_logs (la migración 0003 lo replica).
CallStatus = Literal["ok", "invalid_output", "timeout", "provider_error", "breaker_open", "disabled"]


class AIProviderError(Exception):
    """Fallo del proveedor, ya traducido desde el SDK."""

    def __init__(self, kind: ProviderErrorKind, detail: str = "") -> None:
        super().__init__(f"{kind}: {detail}" if detail else kind)
        self.kind: ProviderErrorKind = kind


class AIInvalidOutput(Exception):
    """La respuesta no es JSON válido o no cumple el esquema / las reglas del caso de uso."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class AIDisabled(Exception):
    pass


class AIBreakerOpen(Exception):
    pass


class AIFailure(Exception):
    """Lo ÚNICO que sale del gateway cuando no hay resultado utilizable."""

    def __init__(self, code: str, call_status: CallStatus, *, attempts: int = 0, latency_ms: int = 0) -> None:
        super().__init__(code)
        self.code = code  # AI_UNAVAILABLE | AI_INVALID_OUTPUT | GENERATION_TIMEOUT
        self.call_status = call_status
        self.attempts = attempts
        self.latency_ms = latency_ms
