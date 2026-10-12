import uuid
from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import delete, exists, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import AcademicProgram, Consent, EmailVerificationToken, User, UserSession


class AuthRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_programs(self) -> Sequence[AcademicProgram]:
        # Collation ICU en español: mismo orden alfabético en Postgres local (Alpine), CI y Supabase.
        result = await self._session.scalars(
            select(AcademicProgram).order_by(AcademicProgram.name.collate("es-x-icu"))
        )
        return result.all()

    async def get_program(self, code: str) -> AcademicProgram | None:
        return await self._session.get(AcademicProgram, code)

    async def email_exists(self, email: str) -> bool:
        return bool(await self._session.scalar(select(exists().where(User.email == email))))

    async def get_pending_user_by_email(self, email: str) -> User | None:
        return await self._session.scalar(
            select(User).where(User.email == email, User.email_verified_at.is_(None))
        )

    async def get_user_with_program(self, user_id: uuid.UUID) -> tuple[User, AcademicProgram] | None:
        row = (
            await self._session.execute(
                select(User, AcademicProgram)
                .join(AcademicProgram, AcademicProgram.code == User.program_code)
                .where(User.id == user_id)
            )
        ).first()
        return (row[0], row[1]) if row else None

    async def get_user_with_program_by_email(self, email: str) -> tuple[User, AcademicProgram] | None:
        row = (
            await self._session.execute(
                select(User, AcademicProgram)
                .join(AcademicProgram, AcademicProgram.code == User.program_code)
                .where(User.email == email)
            )
        ).first()
        return (row[0], row[1]) if row else None

    async def update_password_hash(self, user_id: uuid.UUID, password_hash: str) -> None:
        await self._session.execute(update(User).where(User.id == user_id).values(password_hash=password_hash))

    async def get_active_session(self, token_hash: str, now: datetime) -> tuple[UserSession, User] | None:
        row = (
            await self._session.execute(
                select(UserSession, User)
                .join(User, User.id == UserSession.user_id)
                .where(UserSession.token_hash == token_hash, UserSession.expires_at > now)
            )
        ).first()
        return (row[0], row[1]) if row else None

    async def touch_session(self, session_id: uuid.UUID, now: datetime, expires_at: datetime) -> None:
        await self._session.execute(
            update(UserSession)
            .where(UserSession.id == session_id)
            .values(last_seen_at=now, expires_at=expires_at)
        )

    async def delete_session(self, session_id: uuid.UUID) -> None:
        await self._session.execute(delete(UserSession).where(UserSession.id == session_id))

    async def delete_user(self, user_id: uuid.UUID) -> bool:
        """Borra el usuario; el ON DELETE CASCADE de la BD elimina todo lo que cuelga de él."""
        result = await self._session.execute(
            delete(User).where(User.id == user_id).returning(User.id)
        )
        return result.first() is not None

    async def add_user(self, user: User) -> None:
        self._session.add(user)
        await self._session.flush()

    async def add_consent(self, consent: Consent) -> None:
        self._session.add(consent)

    async def add_verification_token(self, token: EmailVerificationToken) -> None:
        self._session.add(token)

    async def add_session(self, user_session: UserSession) -> None:
        self._session.add(user_session)

    async def consume_verification_token(self, token_hash: str, now: datetime) -> uuid.UUID | None:
        """Marca el token como usado de forma atómica; devuelve el usuario solo si era válido."""
        return await self._session.scalar(
            update(EmailVerificationToken)
            .where(
                EmailVerificationToken.token_hash == token_hash,
                EmailVerificationToken.used_at.is_(None),
                EmailVerificationToken.expires_at > now,
            )
            .values(used_at=now)
            .returning(EmailVerificationToken.user_id)
        )

    async def invalidate_unused_tokens(self, user_id: uuid.UUID, now: datetime) -> None:
        await self._session.execute(
            update(EmailVerificationToken)
            .where(EmailVerificationToken.user_id == user_id, EmailVerificationToken.used_at.is_(None))
            .values(used_at=now)
        )

    async def mark_email_verified(self, user_id: uuid.UUID, now: datetime) -> None:
        await self._session.execute(
            update(User)
            .where(User.id == user_id)
            .values(email_verified_at=func.coalesce(User.email_verified_at, now))
        )
