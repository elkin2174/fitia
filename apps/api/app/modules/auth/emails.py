from html import escape
from urllib.parse import urlencode

from app.core.mailer import EmailMessage


def verification_link(frontend_base_url: str, token: str) -> str:
    # ADR-08: el enlace abre una página del frontend que hace POST /auth/verify-email.
    return f"{frontend_base_url.rstrip('/')}/verificar-correo?{urlencode({'token': token})}"


def build_verification_email(to: str, nickname: str, link: str, ttl_hours: int) -> EmailMessage:
    text = (
        f"Hola, {nickname}:\n\n"
        "Gracias por registrarte en FITIA. Confirma tu correo institucional abriendo este enlace:\n\n"
        f"{link}\n\n"
        f"El enlace vence en {ttl_hours} horas y solo puede usarse una vez. "
        "Si no creaste esta cuenta, ignora este mensaje."
    )
    html = (
        f"<p>Hola, {escape(nickname)}:</p>"
        "<p>Gracias por registrarte en FITIA. Confirma tu correo institucional:</p>"
        f'<p><a href="{escape(link)}">Verificar mi correo</a></p>'
        f"<p>El enlace vence en {ttl_hours} horas y solo puede usarse una vez. "
        "Si no creaste esta cuenta, ignora este mensaje.</p>"
    )
    return EmailMessage(to=to, subject="Confirma tu correo en FITIA", text=text, html=html)
