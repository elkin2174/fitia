import hashlib

from app.core.security import generate_token, hash_password, hash_token, verify_password


def test_hash_password_usa_argon2id_y_verifica() -> None:
    hashed = hash_password("contrasena-segura")

    assert hashed.startswith("$argon2id$")
    assert verify_password(hashed, "contrasena-segura")
    assert not verify_password(hashed, "otra-contrasena")
    assert not verify_password("no-es-un-hash", "contrasena-segura")


def test_generate_token_es_aleatorio_y_largo() -> None:
    tokens = {generate_token() for _ in range(50)}

    assert len(tokens) == 50
    assert all(len(t) >= 43 for t in tokens)  # 32 bytes en base64url


def test_hash_token_es_sha256_hex() -> None:
    assert hash_token("abc") == hashlib.sha256(b"abc").hexdigest()
