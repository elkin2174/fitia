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
