from urllib.parse import parse_qs, urlparse

from app.core.mailer import EmailMessage, Mailer


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
