import hashlib
import secrets

from argon2 import PasswordHasher, Type
from argon2.exceptions import InvalidHashError, VerificationError

# Argon2id con los parámetros recomendados por RFC 9106 (perfil de bajo consumo de memoria).
_password_hasher = PasswordHasher(type=Type.ID)


def hash_password(password: str) -> str:
    return _password_hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _password_hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def generate_token() -> str:
    """Token opaco de 256 bits, apto para URL."""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """SHA-256 hex del token; es lo único que se persiste."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
