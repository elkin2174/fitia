import re

from app.modules.auth.models import ALLOWED_EMAIL_DOMAIN

NICKNAME_MIN = 3
NICKNAME_MAX = 20
PASSWORD_MIN = 8
PASSWORD_MAX = 128
EMAIL_MAX = 254

# Una sola arroba, sin espacios, parte local y dominio no vacíos y dominio con al menos un punto.
_EMAIL_FORMAT_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def normalize_email(raw: str | None) -> str:
    """AC-1-5: se recorta y se pasa a minúsculas antes de cualquier validación."""
    return (raw or "").strip().lower()


def normalize_nickname(raw: str | None) -> str:
    return (raw or "").strip()


def is_valid_email_format(email: str) -> bool:
    return len(email) <= EMAIL_MAX and email.count("@") == 1 and _EMAIL_FORMAT_RE.fullmatch(email) is not None


def has_allowed_domain(email: str) -> bool:
    """AC-1-2: el dominio debe ser exactamente el institucional (sin subdominios ni sufijos)."""
    _, _, domain = email.partition("@")
    return domain == ALLOWED_EMAIL_DOMAIN


def is_valid_nickname(nickname: str) -> bool:
    return NICKNAME_MIN <= len(nickname) <= NICKNAME_MAX
