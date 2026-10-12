import hashlib
import logging
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta

from fastapi import BackgroundTasks
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import Clock
from app.core.config import Settings
from app.core.errors import AppError, FieldError
from app.core.mailer import Mailer, send_safely
from app.core.rate_limit import RateLimiter, enforce_ip_and_email_limits
from app.core.security import generate_token, hash_password, hash_token
from app.modules.auth import validators as v
from app.modules.auth.emails import build_verification_email, verification_link
from app.modules.auth.models import AcademicProgram, Consent, EmailVerificationToken, User, UserSession
from app.modules.auth.repository import AuthRepository
from app.modules.auth.schemas import RegisterRequest

logger = logging.getLogger("fitia.auth")

_EMAIL_UNIQUE_CONSTRAINT = "users_email_key"


@dataclass(frozen=True)
class IssuedSession:
    token: str
    expires_at: datetime


@dataclass(frozen=True)
class VerificationResult:
    user: User
    program: AcademicProgram
    session: IssuedSession


async def issue_session(repository: AuthRepository, user_id: uuid.UUID, now: datetime, ttl_days: int) -> IssuedSession:
    """Crea una sesión opaca (solo se persiste el hash). Reutilizable por el login de HU 2."""
    token = generate_token()
    expires_at = now + timedelta(days=ttl_days)
    await repository.add_session(
        UserSession(user_id=user_id, token_hash=hash_token(token), expires_at=expires_at, last_seen_at=now)
    )
    return IssuedSession(token=token, expires_at=expires_at)


def _email_rate_key(email: str) -> str:
    return hashlib.sha256(email.encode("utf-8")).hexdigest()


def _is_email_unique_violation(exc: IntegrityError) -> bool:
    cause = getattr(exc.orig, "__cause__", None)
    constraint = getattr(cause, "constraint_name", None) or getattr(exc.orig, "constraint_name", None)
    return constraint == _EMAIL_UNIQUE_CONSTRAINT or _EMAIL_UNIQUE_CONSTRAINT in str(exc.orig)


class AuthService:
    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
        clock: Clock,
        mailer: Mailer,
        limiter: RateLimiter,
        background: BackgroundTasks,
    ) -> None:
        self._session = session
        self._repo = AuthRepository(session)
        self._settings = settings
        self._clock = clock
        self._mailer = mailer
        self._limiter = limiter
        self._background = background

    async def list_programs(self) -> Sequence[AcademicProgram]:
        return await self._repo.list_programs()

    async def register(self, data: RegisterRequest, client_ip: str) -> None:
        email = v.normalize_email(data.email)
        nickname = v.normalize_nickname(data.nickname)
        enforce_ip_and_email_limits(self._limiter, self._settings, "register", client_ip, _email_rate_key(email))

        await self._validate_registration(data, email, nickname)

        if not v.has_allowed_domain(email):
            raise AppError(
                422,
                "DOMAIN_NOT_ALLOWED",
                f"Solo se admiten correos @{v.ALLOWED_EMAIL_DOMAIN}",
                [FieldError("email", "DOMAIN_NOT_ALLOWED")],
            )

        if await self._repo.email_exists(email):
            raise self._email_exists_error()

        assert data.password is not None and data.program_code is not None  # garantizado por la validación
        # Argon2id es intensivo en CPU: se calcula fuera del event loop.
        password_hash = await run_in_threadpool(hash_password, data.password)
        now = self._clock.now()
        token = generate_token()
        user = User(
            email=email,
            password_hash=password_hash,
            nickname=nickname,
            program_code=data.program_code,
            created_at=now,
        )
        try:
            # Usuario, consentimiento (HU 8) y token se confirman en una sola transacción.
            await self._repo.add_user(user)
            await self._repo.add_consent(
                Consent(user_id=user.id, text_version=self._settings.CONSENT_TEXT_VERSION, accepted_at=now)
            )
            await self._add_verification_token(user.id, token, now)
            await self._session.commit()
        except IntegrityError as exc:
            await self._session.rollback()
            if _is_email_unique_violation(exc):
                raise self._email_exists_error() from None
            raise

        logger.info("user_registered", extra={"user_id": str(user.id)})
        self._schedule_verification_email(email, nickname, token)

    async def verify_email(self, token: str) -> VerificationResult:
        now = self._clock.now()
        user_id = await self._repo.consume_verification_token(hash_token(token), now)
        if user_id is None:
            raise AppError(
                410,
                "TOKEN_EXPIRED_OR_USED",
                "El enlace de verificación venció o ya fue usado. Solicita uno nuevo para activar tu cuenta.",
            )
        await self._repo.mark_email_verified(user_id, now)
        session = await issue_session(self._repo, user_id, now, self._settings.SESSION_TTL_DAYS)
        found = await self._repo.get_user_with_program(user_id)
        assert found is not None  # el token referencia al usuario con ON DELETE CASCADE
        await self._session.commit()

        logger.info("email_verified", extra={"user_id": str(user_id)})
        user, program = found
        return VerificationResult(user=user, program=program, session=session)

    async def resend_verification(self, raw_email: str | None, client_ip: str) -> None:
        """Responde igual exista o no la cuenta, para no permitir enumeración de correos."""
        email = v.normalize_email(raw_email)
        enforce_ip_and_email_limits(self._limiter, self._settings, "resend", client_ip, _email_rate_key(email))
        if not v.is_valid_email_format(email) or not v.has_allowed_domain(email):
            return

        user = await self._repo.get_pending_user_by_email(email)
        if user is None:
            return

        now = self._clock.now()
        token = generate_token()
        await self._repo.invalidate_unused_tokens(user.id, now)
        await self._add_verification_token(user.id, token, now)
        await self._session.commit()

        logger.info("verification_resent", extra={"user_id": str(user.id)})
        self._schedule_verification_email(email, user.nickname, token)

    async def _validate_registration(self, data: RegisterRequest, email: str, nickname: str) -> None:
        errors: list[FieldError] = []
        if not v.is_valid_nickname(nickname):
            errors.append(FieldError("nickname", "NICKNAME_LENGTH"))
        if not data.program_code or await self._repo.get_program(data.program_code) is None:
            errors.append(FieldError("program_code", "PROGRAM_REQUIRED"))
        if data.accepted_terms is not True:
            errors.append(FieldError("accepted_terms", "TERMS_REQUIRED"))
        if data.password is None or len(data.password) < v.PASSWORD_MIN:
            errors.append(FieldError("password", "WEAK_PASSWORD"))
        elif len(data.password) > v.PASSWORD_MAX:
            errors.append(FieldError("password", "PASSWORD_TOO_LONG"))
        if not v.is_valid_email_format(email):
            errors.append(FieldError("email", "INVALID_EMAIL"))
        if errors:
            raise AppError(422, "VALIDATION_ERROR", self._validation_message(errors), errors)

    @staticmethod
    def _validation_message(errors: list[FieldError]) -> str:
        messages = {
            "NICKNAME_LENGTH": f"El apodo debe tener entre {v.NICKNAME_MIN} y {v.NICKNAME_MAX} caracteres.",
            "PROGRAM_REQUIRED": "Selecciona tu programa académico.",
            "TERMS_REQUIRED": "Debes aceptar el tratamiento de datos para crear la cuenta.",
            "WEAK_PASSWORD": f"La contraseña debe tener al menos {v.PASSWORD_MIN} caracteres.",
            "PASSWORD_TOO_LONG": f"La contraseña no puede superar {v.PASSWORD_MAX} caracteres.",
            "INVALID_EMAIL": "El correo no tiene un formato válido.",
        }
        return " ".join(messages[e.code] for e in errors)

    @staticmethod
    def _email_exists_error() -> AppError:
        return AppError(
            409,
            "EMAIL_EXISTS",
            "Ya existe una cuenta con este correo. Inicia sesión o solicita un nuevo enlace de verificación.",
            [FieldError("email", "EMAIL_EXISTS")],
        )

    async def _add_verification_token(self, user_id: uuid.UUID, token: str, now: datetime) -> None:
        await self._repo.add_verification_token(
            EmailVerificationToken(
                user_id=user_id,
                token_hash=hash_token(token),
                expires_at=now + timedelta(hours=self._settings.VERIFICATION_TOKEN_TTL_HOURS),
            )
        )

    def _schedule_verification_email(self, email: str, nickname: str, token: str) -> None:
        # NFR-01: se envía después de responder, sin bloquear la petición.
        link = verification_link(self._settings.FRONTEND_BASE_URL, token)
        message = build_verification_email(email, nickname, link, self._settings.VERIFICATION_TOKEN_TTL_HOURS)
        self._background.add_task(send_safely, self._mailer, message, "email_verification")
