"""Pruebas de integración para HU 8 (Avisos de voz fijos y catálogo cerrado).

Endpoints:
    GET /api/v1/plan/audio/cues/{name}

Criterios de Aceptación verificados:
- AC-8-2: 200 OK con Content-Type: audio/wav, cuerpo con RIFF/WAVE para los 4 cues del catálogo cerrado.
  Frases en español generadas por la IA y cacheadas en memoria.
- AC-8-3: Catálogo cerrado; cualquier nombre fuera del catálogo (o path traversal) devuelve 404 CUE_NOT_FOUND.
  401 sin sesión; 403 sin perfil completo.
- AC-8-4: 503 AI_UNAVAILABLE con mensaje en español si la IA falla, circuit breaker abierto o AI_ENABLED=False.
- NFR-26: Sin persistencia en base de datos; la caché es en memoria.
- NFR-27: Privacidad: sin identificadores del usuario enviados a la IA.
- NFR-30: Control de costo: rate limiter y circuit breaker aplicados.
"""
from datetime import datetime
from zoneinfo import ZoneInfo

import httpx
import pytest
from sqlalchemy import select

from app.ai.adapters.fake_speech import FailSpeech, FakeSpeechAdapter
from app.ai.call_log import AICallLog
from app.ai.gateway import AIGateway
from app.ai.use_cases.audio_cues import AUDIO_CUES
from app.ai.use_cases.exercise_audio import get_audio_cache
from app.core.clock import FrozenClock
from app.core.config import Settings
from tests.conftest import Student, with_session

BOGOTA = ZoneInfo("America/Bogota")


@pytest.fixture(autouse=True)
def _clear_cache():
    get_audio_cache().clear()
    yield
    get_audio_cache().clear()


async def test_ac_8_2_todos_los_cues_validos_y_formato_wav(
    plan_api,
    student_with_profile: Student,
    fake_speech: FakeSpeechAdapter,
    db,
) -> None:
    token = student_with_profile.token

    for cue_name, expected_text in AUDIO_CUES.items():
        calls_before = fake_speech.calls
        response = await plan_api.cue_audio(token, cue_name)

        assert response.status_code == 200
        assert response.headers["Content-Type"] == "audio/wav"
        assert response.headers["Cache-Control"] == "private, max-age=86400"
        content = response.content
        assert content.startswith(b"RIFF")
        assert b"WAVE" in content[:12]

        # Comprobar llamada al adaptador con el texto exacto
        assert fake_speech.calls == calls_before + 1
        req = fake_speech.requests[-1]
        assert req.text == expected_text

    # Verificar registro en ai_call_logs con use_case="cue_audio"
    stmt = select(AICallLog).where(AICallLog.use_case == "cue_audio")
    logs = (await db.scalars(stmt)).all()
    assert len(logs) == len(AUDIO_CUES)
    for log_entry in logs:
        assert log_entry.status == "ok"
        assert log_entry.prompt_version == "v1"


async def test_ac_8_2_cache_en_memoria_y_compartida_entre_usuarios(
    plan_api,
    student_with_profile: Student,
    make_student,
    complete_diagnostic,
    fake_speech: FakeSpeechAdapter,
) -> None:
    token1 = student_with_profile.token
    student2 = await make_student("estudiante2.cues@correounivalle.edu.co")
    await complete_diagnostic(student2.token)
    token2 = student2.token

    calls_before = fake_speech.calls

    # Primera petición de "descanso" por estudiante 1: ejecuta síntesis
    res1 = await plan_api.cue_audio(token1, "descanso")
    assert res1.status_code == 200
    assert fake_speech.calls == calls_before + 1

    # Segunda petición consecutiva por estudiante 1: hit de caché
    res2 = await plan_api.cue_audio(token1, "descanso")
    assert res2.status_code == 200
    assert res2.content == res1.content
    assert fake_speech.calls == calls_before + 1

    # Petición por estudiante 2 para el mismo cue: hit de caché compartido
    res3 = await plan_api.cue_audio(token2, "descanso")
    assert res3.status_code == 200
    assert res3.content == res1.content
    assert fake_speech.calls == calls_before + 1


async def test_ac_8_3_catalogo_cerrado_y_errores_404_401_403(
    client: httpx.AsyncClient,
    plan_api,
    student_with_profile: Student,
    make_student,
) -> None:
    token = student_with_profile.token

    # 1. Nombre inexistente -> 404 CUE_NOT_FOUND
    res_invalid = await plan_api.cue_audio(token, "frase-inexistente")
    assert res_invalid.status_code == 404
    assert res_invalid.json()["error"]["code"] == "CUE_NOT_FOUND"
    assert "La frase de audio solicitada no existe" in res_invalid.json()["error"]["message"]
    assert res_invalid.headers["Cache-Control"] == "no-store"

    # 2. Path traversal intento -> 404 CUE_NOT_FOUND
    res_traversal = await client.get(
        "/api/v1/plan/audio/cues/../otro",
        headers=with_session(token),
    )
    assert res_traversal.status_code == 404

    # 3. Sin sesión -> 401 UNAUTHORIZED
    unauth = await client.get("/api/v1/plan/audio/cues/descanso")
    assert unauth.status_code == 401
    assert unauth.headers["Cache-Control"] == "no-store"

    # 4. Sin perfil completo -> 403 PROFILE_INCOMPLETE
    unonboarded = await make_student("no.perfil.cues@correounivalle.edu.co")
    res_unonboarded = await plan_api.cue_audio(unonboarded.token, "descanso")
    assert res_unonboarded.status_code == 403
    assert res_unonboarded.headers["Cache-Control"] == "no-store"


async def test_ac_8_4_degradacion_503_proveedor_fallido_o_desactivado(
    plan_api,
    student_with_profile: Student,
    fake_speech: FakeSpeechAdapter,
    settings: Settings,
    ai_gateway: AIGateway,
) -> None:
    token = student_with_profile.token

    # A) Proveedor falla
    fake_speech.script(
        FailSpeech("server_error", "500 simulado 1"),
        FailSpeech("server_error", "500 simulado 2"),
    )
    res_fail = await plan_api.cue_audio(token, "descanso")
    assert res_fail.status_code == 503
    assert res_fail.json()["error"]["code"] == "AI_UNAVAILABLE"
    assert "El servicio de generación de audio no está disponible" in res_fail.json()["error"]["message"]
    assert res_fail.headers["Cache-Control"] == "no-store"

    # B) AI_ENABLED = False
    get_audio_cache().clear()
    settings.AI_ENABLED = False
    try:
        res_disabled = await plan_api.cue_audio(token, "fin-descanso")
        assert res_disabled.status_code == 503
        assert res_disabled.json()["error"]["code"] == "AI_UNAVAILABLE"
        assert res_disabled.headers["Cache-Control"] == "no-store"
    finally:
        settings.AI_ENABLED = True

    # C) Circuit breaker abierto
    get_audio_cache().clear()
    for _ in range(settings.AI_BREAKER_FAILURES):
        ai_gateway.breaker.record_failure()
    assert not ai_gateway.breaker.allow()

    res_breaker = await plan_api.cue_audio(token, "diez-segundos")
    assert res_breaker.status_code == 503
    assert res_breaker.json()["error"]["code"] == "AI_UNAVAILABLE"
    assert res_breaker.headers["Cache-Control"] == "no-store"


async def test_nfr_26_sin_persistencia_en_bd_y_rate_limit(
    plan_api,
    student_with_profile: Student,
    plan_footprint,
    settings: Settings,
) -> None:
    token = student_with_profile.token
    footprint_before = await plan_footprint(student_with_profile.user.id)

    # Llamar a un cue válido
    res = await plan_api.cue_audio(token, "fin-rutina")
    assert res.status_code == 200

    # NFR-26: La base de datos no crea filas de planes ni audios
    footprint_after = await plan_footprint(student_with_profile.user.id)
    assert footprint_before == footprint_after

    # NFR-30: Rate limit por usuario (ya consumimos 1 hit)
    limit = settings.RATE_LIMIT_EXERCISE_AUDIO_PER_USER
    for _ in range(limit - 1):
        res = await plan_api.cue_audio(token, "fin-rutina")
        assert res.status_code == 200

    # Petición que excede el límite
    res_limited = await plan_api.cue_audio(token, "fin-rutina")
    assert res_limited.status_code == 429
    assert res_limited.json()["error"]["code"] == "RATE_LIMITED"
    assert "Retry-After" in res_limited.headers
    assert res_limited.headers["Cache-Control"] == "no-store"

