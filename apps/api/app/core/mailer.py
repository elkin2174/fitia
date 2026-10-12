import logging
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass
from functools import lru_cache

import httpx

from app.core.config import Settings, get_settings

logger = logging.getLogger("fitia.mailer")


@dataclass(frozen=True)
class EmailMessage:
    to: str
    subject: str
    text: str
    html: str


class Mailer(ABC):
    """Puerto de correo transaccional (ADR-12)."""

    @abstractmethod
    async def send(self, message: EmailMessage) -> None: ...


class ConsoleMailer(Mailer):
    """Solo desarrollo local: escribe el correo en stdout, fuera del sistema de logs."""

    async def send(self, message: EmailMessage) -> None:
        sys.stdout.write(f"\n--- [ConsoleMailer] {message.subject} ---\n{message.text}\n---\n")
        sys.stdout.flush()


class HttpMailer(Mailer):
    """Proveedor por API HTTP compatible con Resend (POST JSON con Bearer)."""

    def __init__(self, api_url: str, api_key: str, sender: str, timeout: float = 10.0) -> None:
        self._api_url = api_url
        self._api_key = api_key
        self._sender = sender
        self._timeout = timeout

    async def send(self, message: EmailMessage) -> None:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(
                self._api_url,
                headers={"Authorization": f"Bearer {self._api_key}"},
                json={
                    "from": self._sender,
                    "to": [message.to],
                    "subject": message.subject,
                    "text": message.text,
                    "html": message.html,
                },
            )
            response.raise_for_status()


def build_mailer(settings: Settings) -> Mailer:
    if settings.MAIL_PROVIDER == "http":
        return HttpMailer(settings.MAIL_API_URL, settings.MAIL_API_KEY, settings.MAIL_FROM)
    return ConsoleMailer()


@lru_cache
def get_mailer() -> Mailer:
    return build_mailer(get_settings())


async def send_safely(mailer: Mailer, message: EmailMessage, purpose: str) -> None:
    """Envío en segundo plano: un fallo del proveedor nunca se propaga al cliente."""
    try:
        await mailer.send(message)
        logger.info("email_sent", extra={"purpose": purpose})
    except Exception as exc:  # noqa: BLE001 - cualquier fallo del proveedor se registra y se descarta
        logger.error("email_failed", extra={"purpose": purpose, "error_type": type(exc).__name__})
