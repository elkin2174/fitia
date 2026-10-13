import uuid
from collections.abc import Awaitable, Callable
from urllib.parse import parse_qs, urlparse

from app.core.mailer import EmailMessage, Mailer
from app.modules.onboarding.status import OnboardingStatus
from app.modules.plan.runner import PlanJobScheduler


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


class FakeMonotonic:
    """Reloj monotónico falso para el gateway: `sleep` avanza el tiempo sin esperar."""

    def __init__(self, start: float = 1000.0) -> None:
        self.now = start
        self.sleeps: list[float] = []

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds

    async def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


class ManualScheduler(PlanJobScheduler):
    """Guarda los trabajos y los ejecuta cuando el test lo pide (permite observar `generating`)."""

    def __init__(self) -> None:
        self.jobs: list[Callable[[], Awaitable[None]]] = []

    def schedule(self, job: Callable[[], Awaitable[None]]) -> None:
        self.jobs.append(job)

    @property
    def pending(self) -> int:
        return len(self.jobs)

    async def run_next(self) -> None:
        await self.jobs.pop(0)()

    async def run_all(self) -> None:
        while self.jobs:
            await self.run_next()
