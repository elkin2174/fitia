import hashlib
import logging
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal

from fastapi import BackgroundTasks
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import Clock
from app.core.config import Settings
from app.core.errors import AppError, FieldError
from app.core.mailer import Mailer, send_safely
from app.core.rate_limit import RateLimiter, enforce_ip_and_email_limits
from app.core.security import generate_token, hash_password, hash_token, password_needs_rehash, verify_password
from app.modules.auth import validators as v
from app.modules.auth.emails import build_verification_email, verification_link
from app.modules.auth.models import AcademicProgram, Consent, EmailVerificationToken, User, UserSession
from app.modules.auth.repository import AuthRepository
from app.modules.auth.schemas import LoginRequest, RegisterRequest
from app.modules.onboarding.status import OnboardingStatus

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


@dataclass(frozen=True)
class LoginResult:
    user: User
    program: AcademicProgram
    session: IssuedSession
    next: Literal["onboarding", "home"]


@dataclass(frozen=True)
class MeResult:
    user: User
    program: AcademicProgram
    onboarding_completed: bool


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
        onboarding: OnboardingStatus,
    ) -> None:
        self._session = session
        self._repo = AuthRepository(session)
        self._settings = settings
        self._clock = clock
        self._mailer = mailer
        self._limiter = limiter
        self._background = background
        self._onboarding = onboarding

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

    async def login(self, data: LoginRequest, client_ip: str) -> LoginResult:
        email = v.normalize_email(data.email)
        failures_key = f"login:fail:{_email_rate_key(email)}"
        window = self._settings.RATE_LIMIT_LOGIN_WINDOW_MINUTES * 60
        # El límite va antes de cualquier consulta o Argon2 para que el login no sea un vector de DoS.
        self._limiter.hit(f"login:ip:{client_ip}", self._settings.RATE_LIMIT_LOGIN_PER_IP, window)
        self._limiter.check(failures_key, self._settings.RATE_LIMIT_LOGIN_PER_EMAIL, window)

        self._validate_login(data, email)
        assert data.password is not None  # garantizado por la validación

        found = await self._repo.get_user_with_program_by_email(email) if v.has_allowed_domain(email) else None
        if found is None:
            self._limiter.record(failures_key, window)
            logger.info("login_failed", extra={"reason": "account_not_found"})
            raise AppError(
                404,
                "ACCOUNT_NOT_FOUND",
                "Este correo no está registrado en FITIA. Crea una cuenta para empezar.",
                [FieldError("email", "ACCOUNT_NOT_FOUND")],
            )
        user, program = found

        if not await run_in_threadpool(verify_password, user.password_hash, data.password):
            self._limiter.record(failures_key, window)
            logger.info("login_failed", extra={"reason": "invalid_credentials", "user_id": str(user.id)})
            raise AppError(401, "INVALID_CREDENTIALS", "El correo o la contraseña no son correctos.")

        # Solo quien conoce la contraseña llega aquí: el estado de verificación no se puede sondear.
        if user.email_verified_at is None:
            logger.info("login_failed", extra={"reason": "email_not_verified", "user_id": str(user.id)})
            raise AppError(
                403,
                "EMAIL_NOT_VERIFIED",
                "Debes verificar tu correo antes de iniciar sesión. Revisa tu bandeja o solicita un nuevo enlace.",
            )

        if password_needs_rehash(user.password_hash):
            new_hash = await run_in_threadpool(hash_password, data.password)
            await self._repo.update_password_hash(user.id, new_hash)

        # Siempre una sesión nueva (evita fijación de sesión); se admiten varias por usuario.
        session = await issue_session(self._repo, user.id, self._clock.now(), self._settings.SESSION_TTL_DAYS)
        await self._session.commit()
        self._limiter.clear(failures_key)

        completed = await self._onboarding.is_completed(user.id)
        logger.info("login_succeeded", extra={"user_id": str(user.id)})
        return LoginResult(user=user, program=program, session=session, next="home" if completed else "onboarding")

    async def get_me(self, user_id: uuid.UUID) -> MeResult:
        found = await self._repo.get_user_with_program(user_id)
        assert found is not None  # el guard de sesión ya comprobó que el usuario existe
        user, program = found
        return MeResult(user=user, program=program, onboarding_completed=await self._onboarding.is_completed(user_id))

    def _validate_login(self, data: LoginRequest, email: str) -> None:
        errors: list[FieldError] = []
        if not v.is_valid_email_format(email):
            errors.append(FieldError("email", "INVALID_EMAIL"))
        if not data.password:
            errors.append(FieldError("password", "REQUIRED"))
        elif len(data.password) > v.PASSWORD_MAX:
            errors.append(FieldError("password", "PASSWORD_TOO_LONG"))
        if errors:
            raise AppError(422, "VALIDATION_ERROR", self._validation_message(errors), errors)

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
            "REQUIRED": "Escribe tu contraseña.",
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
