import uuid
from urllib.parse import parse_qs, urlparse

from app.core.mailer import EmailMessage, Mailer
from app.modules.onboarding.status import OnboardingStatus


class FakeMailer(Mailer):
    """Captura los correos en memoria en lugar de enviarlos."""

    def __init__(self) -> None:
        self.sent: list[EmailMessage] = []

    async def send(self, message: EmailMessage) -> None:
        self.sent.append(message)

    def last_link(self) -> str:
        assert self.sent, "no se envió ningún correo"
        line = next(ln for ln in self.sent[-1].text.splitlines() if "/verificar-correo?" in ln)
        return line.strip()

    def last_token(self) -> str:
        return parse_qs(urlparse(self.last_link()).query)["token"][0]


class FakeOnboardingStatus(OnboardingStatus):
    def __init__(self, completed: bool) -> None:
        self.completed = completed

    async def is_completed(self, user_id: uuid.UUID) -> bool:
        return self.completed
