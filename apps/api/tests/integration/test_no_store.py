"""NFR-11: `Cache-Control: no-store` en todas las respuestas autenticadas, incluidas las de error."""
import httpx
import pytest

from tests.conftest import SeededUser, session_token, with_session

# (método, ruta, kwargs de la petición, ¿con sesión?, ¿con CSRF?, estado esperado)
AUTHENTICATED_CASES = [
    ("GET", "/api/v1/me", {}, True, True, 200),
    ("GET", "/api/v1/me", {}, False, True, 401),
    ("POST", "/api/v1/auth/logout", {}, True, True, 204),
    ("POST", "/api/v1/auth/logout", {}, False, True, 401),
    ("POST", "/api/v1/auth/logout", {}, True, False, 403),
    ("POST", "/api/v1/me/delete-account", {"json": {"confirm": True}}, True, True, 204),
    ("POST", "/api/v1/me/delete-account", {"json": {}}, True, True, 400),
    ("POST", "/api/v1/me/delete-account", {"json": {"confirm": "si"}}, True, True, 422),
    ("POST", "/api/v1/me/delete-account", {"json": {"confirm": True}}, False, True, 401),
    ("GET", "/api/v1/ruta-que-no-existe", {}, True, True, 404),
]


@pytest.mark.parametrize(
    ("method", "url", "kwargs", "with_cookie", "with_csrf", "expected"),
    AUTHENTICATED_CASES,
    ids=[f"{m} {u.removeprefix('/api/v1')} {e}" for m, u, _, _, _, e in AUTHENTICATED_CASES],
)
async def test_nfr_11_respuestas_autenticadas_llevan_no_store(
    client: httpx.AsyncClient,
    login,
    verified_user: SeededUser,
    method: str,
    url: str,
    kwargs: dict,
    with_cookie: bool,
    with_csrf: bool,
    expected: int,
) -> None:
    headers: dict[str, str] = {}
    if with_cookie:
        headers.update(with_session(session_token(await login(verified_user.email))))
    if not with_csrf:
        headers["X-Requested-With"] = ""

    response = await client.request(method, url, headers=headers, **kwargs)

    assert response.status_code == expected
    assert response.headers["Cache-Control"] == "no-store"


@pytest.mark.parametrize("url", ["/api/v1/programs", "/api/v1/health", "/health"])
async def test_nfr_11_rutas_publicas_cacheables_no_se_ven_afectadas(client: httpx.AsyncClient, url: str) -> None:
    response = await client.get(url)

    assert response.status_code == 200
    assert "cache-control" not in response.headers


async def test_nfr_11_mutaciones_publicas_tambien_son_no_store(client: httpx.AsyncClient) -> None:
    response = await client.post("/api/v1/auth/login", json={})

    assert response.status_code == 422
    assert response.headers["Cache-Control"] == "no-store"


async def test_nfr_11_audio_permite_private_y_errores_mantienen_no_store(
    client: httpx.AsyncClient,
    login,
    verified_user: SeededUser,
) -> None:
    # En endpoints de audio, las respuestas de error continúan con no-store
    dummy_id = "00000000-0000-0000-0000-000000000000"
    unauth = await client.get(f"/api/v1/plan/exercises/{dummy_id}/audio")
    assert unauth.status_code == 401
    assert unauth.headers["Cache-Control"] == "no-store"

    headers = with_session(session_token(await login(verified_user.email)))
    res_err = await client.get(f"/api/v1/plan/exercises/{dummy_id}/audio", headers=headers)
    assert res_err.status_code == 403
    assert res_err.headers["Cache-Control"] == "no-store"
