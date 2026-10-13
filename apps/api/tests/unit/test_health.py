import httpx

from app.main import app


async def _get(path: str) -> httpx.Response:
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        return await client.get(path)


async def test_health_endpoint() -> None:
    response = await _get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "app": "FITIA API", "version": "1.0.0"}


async def test_api_v1_health_endpoint() -> None:
    response = await _get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "api_version": "v1"}


async def test_ruta_inexistente_usa_formato_uniforme() -> None:
    response = await _get("/api/v1/no-existe")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"
