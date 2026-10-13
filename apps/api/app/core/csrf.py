from fastapi import Request

from app.core.errors import AppError

CSRF_HEADER = "X-Requested-With"
CSRF_HEADER_VALUE = "fitia"
_SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


async def require_csrf_header(request: Request) -> None:
    """Las mutaciones deben llevar un encabezado que un formulario cross-site no puede enviar."""
    if request.method in _SAFE_METHODS:
        return
    if request.headers.get(CSRF_HEADER) != CSRF_HEADER_VALUE:
        raise AppError(403, "CSRF_HEADER_MISSING", f"Falta el encabezado {CSRF_HEADER}: {CSRF_HEADER_VALUE}.")
