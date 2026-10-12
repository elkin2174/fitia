import pytest

from app.modules.auth import validators as v


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("  Ana@CorreoUnivalle.EDU.CO ", "ana@correounivalle.edu.co"),
        ("\tana@correounivalle.edu.co\n", "ana@correounivalle.edu.co"),
        (None, ""),
    ],
)
def test_normalize_email(raw: str | None, expected: str) -> None:
    assert v.normalize_email(raw) == expected


@pytest.mark.parametrize(
    ("email", "valid"),
    [
        ("ana@correounivalle.edu.co", True),
        ("ana.maria+fitia@correounivalle.edu.co", True),
        ("ana", False),
        ("ana@", False),
        ("@correounivalle.edu.co", False),
        ("a@b@correounivalle.edu.co", False),
        ("ana gomez@correounivalle.edu.co", False),
        ("ana@localhost", False),
        ("a" * 250 + "@correounivalle.edu.co", False),
    ],
)
def test_is_valid_email_format(email: str, valid: bool) -> None:
    assert v.is_valid_email_format(email) is valid


@pytest.mark.parametrize(
    ("email", "allowed"),
    [
        ("ana@correounivalle.edu.co", True),
        ("ana@gmail.com", False),
        ("ana@correounivalle.edu.co.evil.com", False),
        ("ana@sub.correounivalle.edu.co", False),
        ("ana@evilcorreounivalle.edu.co", False),
        ("ana@correounivalle.edu.co.", False),
    ],
)
def test_has_allowed_domain_exige_dominio_exacto(email: str, allowed: bool) -> None:
    assert v.has_allowed_domain(email) is allowed


@pytest.mark.parametrize(("nickname", "valid"), [("ab", False), ("abc", True), ("a" * 20, True), ("a" * 21, False)])
def test_is_valid_nickname(nickname: str, valid: bool) -> None:
    assert v.is_valid_nickname(nickname) is valid


def test_normalize_nickname_recorta_espacios() -> None:
    assert v.normalize_nickname("  Pantera  ") == "Pantera"
    assert v.normalize_nickname(None) == ""
