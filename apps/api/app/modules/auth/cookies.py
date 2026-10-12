from datetime import UTC, datetime

from fastapi import Response

from app.core.config import Settings

SESSION_COOKIE_NAME = "fitia_session"


def set_session_cookie(response: Response, token: str, expires_at: datetime, settings: Settings) -> None:
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        max_age=settings.SESSION_TTL_DAYS * 24 * 60 * 60,
        expires=expires_at.astimezone(UTC),
        path="/",
        secure=settings.COOKIE_SECURE,
        httponly=True,
        samesite="lax",
    )


def delete_session_cookie(response: Response, settings: Settings) -> None:
    response.delete_cookie(
        key=SESSION_COOKIE_NAME, path="/", secure=settings.COOKIE_SECURE, httponly=True, samesite="lax"
    )


def session_cookie_deletion_header(settings: Settings) -> str:
    """Valor de Set-Cookie que borra la sesión, para respuestas de error que no pasan por `Response`."""
    response = Response()
    delete_session_cookie(response, settings)
    return response.headers["set-cookie"]
