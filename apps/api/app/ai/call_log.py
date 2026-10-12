"""Métricas de llamadas a la IA: sin user_id y sin contenido (ni prompt ni respuesta)."""
import logging
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Integer, SmallInteger, Text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base

logger = logging.getLogger("fitia.ai")

CALL_STATUSES: tuple[str, ...] = ("ok", "invalid_output", "timeout", "provider_error", "breaker_open", "disabled")


class AICallLog(Base):
    __tablename__ = "ai_call_logs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('ok', 'invalid_output', 'timeout', 'provider_error', 'breaker_open', 'disabled')",
            name="ck_ai_call_logs_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    use_case: Mapped[str] = mapped_column(Text, nullable=False)
    prompt_version: Mapped[str] = mapped_column(Text, nullable=False)
    model: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    attempts: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


@dataclass(frozen=True)
class CallLogEntry:
    use_case: str
    prompt_version: str
    model: str
    status: str
    latency_ms: int
    attempts: int
    created_at: datetime


class CallRecorder(ABC):
    @abstractmethod
    async def record(self, entry: CallLogEntry) -> None: ...


class DbCallRecorder(CallRecorder):
    """Escribe con una sesión corta PROPIA: la métrica persiste aunque el guardado del plan falle."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def record(self, entry: CallLogEntry) -> None:
        try:
            async with self._session_factory() as session:
                session.add(AICallLog(**entry.__dict__))
                await session.commit()
        except Exception as exc:  # noqa: BLE001 - una métrica nunca debe romper la generación
            logger.error("ai_call_log_failed", extra={"error_type": type(exc).__name__})


class MemoryCallRecorder(CallRecorder):
    """Para pruebas y el script de humo."""

    def __init__(self) -> None:
        self.entries: list[CallLogEntry] = []

    async def record(self, entry: CallLogEntry) -> None:
        self.entries.append(entry)
