"""Guards de sesión reutilizables por todas las HU que exponen datos del usuario (NFR-10)."""
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

from fastapi import Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import Clock, get_clock
from app.core.config import Settings, get_settings
from app.core.db import get_session
from app.core.errors import AppError
from app.core.security import hash_token
from app.modules.auth.cookies import SESSION_COOKIE_NAME, session_cookie_deletion_header, set_session_cookie
from app.modules.auth.repository import AuthRepository
from app.modules.onboarding.status import OnboardingStatus, get_onboarding_status


@dataclass(frozen=True)
class CurrentUser:
    id: uuid.UUID
    nickname: str
    program_code: str
    role: str


@dataclass(frozen=True)
class CurrentSession:
    id: uuid.UUID
    expires_at: datetime
    user: CurrentUser


def _unauthenticated(settings: Settings) -> AppError:
    return AppError(
        401,
        "UNAUTHENTICATED",
        "Debes iniciar sesión para continuar.",
        headers={"Set-Cookie": session_cookie_deletion_header(settings), "Cache-Control": "no-store"},
    )


async def get_current_session(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
    clock: Clock = Depends(get_clock),
) -> CurrentSession:
    """Resuelve la sesión desde la cookie. Sin sesión válida → 401 y la cookie se borra."""
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        raise _unauthenticated(settings)

    now = clock.now()
    repo = AuthRepository(db)
    found = await repo.get_active_session(hash_token(token), now)
    if found is None:
        raise _unauthenticated(settings)
    user_session, user = found
    if user.email_verified_at is None:
        raise _unauthenticated(settings)

    expires_at = user_session.expires_at
    if now - user_session.last_seen_at >= timedelta(minutes=settings.SESSION_TOUCH_INTERVAL_MINUTES):
        # Expiración deslizante, con escritura limitada a una vez por intervalo.
        expires_at = now + timedelta(days=settings.SESSION_TTL_DAYS)
        await repo.touch_session(user_session.id, now, expires_at)
        await db.commit()
        set_session_cookie(response, token, expires_at, settings)

    response.headers["Cache-Control"] = "no-store"  # NFR-11: nada autenticado se guarda en caché
    return CurrentSession(
        id=user_session.id,
        expires_at=expires_at,
        user=CurrentUser(id=user.id, nickname=user.nickname, program_code=user.program_code, role=user.role),
    )


async def get_current_user(current: CurrentSession = Depends(get_current_session)) -> CurrentUser:
    return current.user


async def require_complete_profile(
    user: CurrentUser = Depends(get_current_user),
    onboarding: OnboardingStatus = Depends(get_onboarding_status),
) -> CurrentUser:
    """Guard "S+P": sesión válida y diagnóstico inicial (HU 4) completo."""
    if not await onboarding.is_completed(user.id):
        raise AppError(403, "ONBOARDING_REQUIRED", "Completa tu diagnóstico inicial para continuar.")
    return user
