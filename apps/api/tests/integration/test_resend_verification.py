"""HU 1 - Reenvío del enlace (AC-1-8) sin permitir enumeración de cuentas."""
import httpx
import pytest

from tests.fakes import FakeMailer

RESEND_URL = "/api/v1/auth/resend-verification"
VERIFY_URL = "/api/v1/auth/verify-email"
EMAIL = "ana.gomez@correounivalle.edu.co"


async def test_respuesta_identica_exista_o_no_la_cuenta(
    client: httpx.AsyncClient, register, mailer: FakeMailer
) -> None:
    await register()
    mailer.sent.clear()

    existing = await client.post(RESEND_URL, json={"email": EMAIL})
    missing = await client.post(RESEND_URL, json={"email": "nadie@correounivalle.edu.co"})
    other_domain = await client.post(RESEND_URL, json={"email": "nadie@gmail.com"})
    empty = await client.post(RESEND_URL, json={})

    for response in (existing, missing, other_domain, empty):
        assert response.status_code == 202
        assert response.json() == existing.json()
    assert [m.to for m in mailer.sent] == [EMAIL]


async def test_reenvio_invalida_el_token_anterior(client: httpx.AsyncClient, register, mailer: FakeMailer) -> None:
    await register()
    old_token = mailer.last_token()

    await client.post(RESEND_URL, json={"email": "  ANA.GOMEZ@correounivalle.edu.co "})
    new_token = mailer.last_token()

    assert new_token != old_token
    assert (await client.post(VERIFY_URL, json={"token": old_token})).status_code == 410
    assert (await client.post(VERIFY_URL, json={"token": new_token})).status_code == 200


async def test_cuenta_ya_verificada_no_recibe_enlace(client: httpx.AsyncClient, register, mailer: FakeMailer) -> None:
    await register()
    await client.post(VERIFY_URL, json={"token": mailer.last_token()})
    mailer.sent.clear()

    response = await client.post(RESEND_URL, json={"email": EMAIL})

    assert response.status_code == 202
    assert mailer.sent == []


async def test_reenvio_aplica_rate_limit(client: httpx.AsyncClient, register) -> None:
    await register()
    statuses = [(await client.post(RESEND_URL, json={"email": EMAIL})).status_code for _ in range(6)]

    assert statuses[:5] == [202] * 5
    assert statuses[5] == 429


@pytest.mark.parametrize("email", [EMAIL, "nadie@correounivalle.edu.co"])
async def test_rate_limit_del_reenvio_no_distingue_si_la_cuenta_existe(
    client: httpx.AsyncClient, register, email: str
) -> None:
    await register()
    statuses = [(await client.post(RESEND_URL, json={"email": email})).status_code for _ in range(6)]

    assert statuses == [202] * 5 + [429]
