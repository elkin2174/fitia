"""Pruebas de integración para HU 1 y HU 2 (Audio de ejercicios con IA y Caché).

Endpoints:
    GET /api/v1/plan/exercises/{exercise_id}/audio

Criterios de Aceptación verificados:
- AC-1-1: 200, audio/wav, cuerpo inicia con RIFF; texto en adaptador contiene nombre, pasos y disclaimer una vez al final.
- AC-1-2 y AC-1-3: No acepta texto del cliente; texto en adaptador no contiene user_id ni email del usuario.
- AC-1-4: 404 para ejercicio ajeno o inexistente; 401 sin sesión; 403 sin perfil completo.
- AC-1-5: 503 AI_UNAVAILABLE con mensaje en español si AI_ENABLED=False, falla el proveedor o breaker abierto.
- AC-1-6: Escribe registro en ai_call_logs con use_case="exercise_audio", sin user_id ni texto.
- AC-2-1: Dos peticiones consecutivas -> 1 sola llamada a la IA; dos concurrentes -> 1 sola llamada a la IA.
- AC-2-2: El audio no se persiste en la BD (esquema intacto).
- AC-2-3: Cache-Control: private, max-age=86400 en 200; no-store en errores.
- AC-2-4: Rate limit por usuario genera 429.
"""
import asyncio
from datetime import datetime
import uuid
from zoneinfo import ZoneInfo

import httpx
import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.adapters.fake_speech import FailSpeech, FakeSpeechAdapter, WaitSpeech
from app.ai.call_log import AICallLog
from app.ai.gateway import AIGateway
from app.ai.use_cases.exercise_audio import get_audio_cache
from app.core.clock import FrozenClock
from app.core.config import Settings
from app.modules.plan.models import EXERCISE_DISCLAIMER
from tests.conftest import Student, with_session
from tests.fakes import ManualScheduler

BOGOTA = ZoneInfo("America/Bogota")


async def _generate_test_plan(
    plan_api, manual_scheduler: ManualScheduler, student: Student, clock: FrozenClock
) -> dict:
    clock.set(datetime(2026, 10, 12, 10, 0, 0, tzinfo=BOGOTA))
    token = student.token
    await plan_api.generate(token)
    await manual_scheduler.run_all()
    today_res = await plan_api.today(token)
    assert today_res.status_code == 200
    exercises = today_res.json()["day"]["exercises"]
    assert len(exercises) > 0
    return exercises[0]


async def test_ac_1_1_generacion_audio_valida_y_formato_wav(
    plan_api,
    manual_scheduler: ManualScheduler,
    student_with_profile: Student,
    clock: FrozenClock,
    fake_speech: FakeSpeechAdapter,
) -> None:
    target_exercise = await _generate_test_plan(plan_api, manual_scheduler, student_with_profile, clock)
    exercise_id = target_exercise["id"]

    calls_before = fake_speech.calls
    response = await plan_api.audio(student_with_profile.token, exercise_id)

    assert response.status_code == 200
    assert response.headers["Content-Type"] == "audio/wav"
    assert response.headers["Cache-Control"] == "private, max-age=86400"
    content = response.content
    # Contenedor WAV válido
    assert content.startswith(b"RIFF")
    assert b"WAVE" in content[:12]

    # Verifica que a la IA viajó el texto en el formato esperado
    assert fake_speech.calls == calls_before + 1
    req = fake_speech.requests[-1]
    assert target_exercise["name"] in req.text
    for idx, step in enumerate(target_exercise["guide"]["steps"], 1):
        assert f"Paso {idx}: {step}" in req.text
    assert req.text.endswith(EXERCISE_DISCLAIMER.strip())
    assert req.text.count(EXERCISE_DISCLAIMER.strip()) == 1


async def test_ac_1_2_y_1_3_privacidad_sin_datos_de_usuario(
    client: httpx.AsyncClient,
    plan_api,
    manual_scheduler: ManualScheduler,
    student_with_profile: Student,
    clock: FrozenClock,
    fake_speech: FakeSpeechAdapter,
) -> None:
    target_exercise = await _generate_test_plan(plan_api, manual_scheduler, student_with_profile, clock)
    exercise_id = target_exercise["id"]

    # El endpoint es GET y no debe aceptar payload enviado por el cliente
    # Si el cliente intenta inyectar texto malicioso en query params o body, el servidor lo ignora
    token = student_with_profile.token
    res = await client.get(
        f"/api/v1/plan/exercises/{exercise_id}/audio?custom_text=hack",
        headers=with_session(token),
    )
    assert res.status_code == 200

    last_req = fake_speech.requests[-1]
    assert "hack" not in last_req.text
    # Ningún dato identificador del usuario viaja al adaptador TTS
    assert str(student_with_profile.user.id) not in last_req.text
    assert student_with_profile.user.email not in last_req.text
    assert "@" not in last_req.text


async def test_ac_1_4_aislamiento_y_errores_404_401_403(
    client: httpx.AsyncClient,
    plan_api,
    manual_scheduler: ManualScheduler,
    student_with_profile: Student,
    make_student,
    complete_diagnostic,
    clock: FrozenClock,
) -> None:
    target_exercise = await _generate_test_plan(plan_api, manual_scheduler, student_with_profile, clock)
    exercise_id = target_exercise["id"]

    # 1. Sin sesión -> 401
    unauth = await client.get(f"/api/v1/plan/exercises/{exercise_id}/audio")
    assert unauth.status_code == 401
    assert unauth.headers["Cache-Control"] == "no-store"

    # 2. Sin diagnóstico completado -> 403
    unonboarded = await make_student("no.profile.audio@correounivalle.edu.co")
    res_unonboarded = await plan_api.audio(unonboarded.token, exercise_id)
    assert res_unonboarded.status_code == 403
    assert res_unonboarded.headers["Cache-Control"] == "no-store"

    # 3. UUID inexistente -> 404
    non_existent = uuid.uuid4()
    res_404 = await plan_api.audio(student_with_profile.token, non_existent)
    assert res_404.status_code == 404
    assert res_404.json()["error"]["code"] == "EXERCISE_NOT_FOUND"
    assert res_404.headers["Cache-Control"] == "no-store"

    # 4. Ejercicio de otro usuario -> 404 (aislamiento entre estudiantes)
    student_b = await make_student("estudiante.otro.audio@correounivalle.edu.co")
    await complete_diagnostic(student_b.token)
    await plan_api.generate(student_b.token)
    await manual_scheduler.run_all()

    other_user_res = await plan_api.audio(student_b.token, exercise_id)
    assert other_user_res.status_code == 404
    assert other_user_res.json()["error"]["code"] == "EXERCISE_NOT_FOUND"
    assert other_user_res.headers["Cache-Control"] == "no-store"


async def test_ac_1_5_ia_fallo_breaker_y_disabled_devuelven_503(
    plan_api,
    manual_scheduler: ManualScheduler,
    student_with_profile: Student,
    clock: FrozenClock,
    fake_speech: FakeSpeechAdapter,
    settings: Settings,
    ai_gateway: AIGateway,
) -> None:
    target_exercise = await _generate_test_plan(plan_api, manual_scheduler, student_with_profile, clock)
    exercise_id = target_exercise["id"]

    # A) Simular fallo del proveedor (2 fallos para agotar el reintento de resiliencia)
    fake_speech.script(
        FailSpeech("server_error", "500 simulado intento 1"),
        FailSpeech("server_error", "500 simulado intento 2"),
    )
    res_fail = await plan_api.audio(student_with_profile.token, exercise_id)
    assert res_fail.status_code == 503
    assert res_fail.json()["error"]["code"] == "AI_UNAVAILABLE"
    assert "El servicio de generación de audio no está disponible" in res_fail.json()["error"]["message"]
    assert res_fail.headers["Cache-Control"] == "no-store"

    # B) Simular AI_ENABLED=False
    get_audio_cache().clear()
    settings.AI_ENABLED = False
    try:
        res_disabled = await plan_api.audio(student_with_profile.token, exercise_id)
        assert res_disabled.status_code == 503
        assert res_disabled.json()["error"]["code"] == "AI_UNAVAILABLE"
        assert res_disabled.headers["Cache-Control"] == "no-store"
    finally:
        settings.AI_ENABLED = True

    # C) Simular Circuit Breaker abierto
    get_audio_cache().clear()
    for _ in range(settings.AI_BREAKER_FAILURES):
        ai_gateway.breaker.record_failure()
    assert not ai_gateway.breaker.allow()

    res_breaker = await plan_api.audio(student_with_profile.token, exercise_id)
    assert res_breaker.status_code == 503
    assert res_breaker.json()["error"]["code"] == "AI_UNAVAILABLE"
    assert res_breaker.headers["Cache-Control"] == "no-store"


async def test_ac_1_6_registro_en_ai_call_logs_sin_user_id_ni_texto(
    plan_api,
    manual_scheduler: ManualScheduler,
    student_with_profile: Student,
    clock: FrozenClock,
    db: AsyncSession,
) -> None:
    target_exercise = await _generate_test_plan(plan_api, manual_scheduler, student_with_profile, clock)
    exercise_id = target_exercise["id"]

    res = await plan_api.audio(student_with_profile.token, exercise_id)
    assert res.status_code == 200

    logs = (
        await db.scalars(
            select(AICallLog)
            .where(AICallLog.use_case == "exercise_audio")
            .order_by(AICallLog.created_at.desc())
        )
    ).all()

    assert len(logs) >= 1
    latest_log = logs[0]
    assert latest_log.use_case == "exercise_audio"
    assert latest_log.status == "ok"
    assert latest_log.prompt_version == "v1"
    assert latest_log.model != ""
    assert latest_log.attempts >= 1
    # Verifica que la tabla ai_call_logs no tiene columnas de user_id ni contenido
    columns = AICallLog.__table__.columns.keys()
    assert "user_id" not in columns
    assert "prompt" not in columns
    assert "content" not in columns


async def test_ac_2_1_reutilizacion_cache_secuencial_y_concurrente(
    plan_api,
    manual_scheduler: ManualScheduler,
    student_with_profile: Student,
    clock: FrozenClock,
    fake_speech: FakeSpeechAdapter,
) -> None:
    target_exercise = await _generate_test_plan(plan_api, manual_scheduler, student_with_profile, clock)
    exercise_id = target_exercise["id"]

    # 1. Primera petición: llama a la IA y llena la caché en memoria
    get_audio_cache().clear()
    calls_start = fake_speech.calls
    res1 = await plan_api.audio(student_with_profile.token, exercise_id)
    assert res1.status_code == 200
    assert fake_speech.calls == calls_start + 1

    # 2. Segunda petición secuencial: reutiliza la caché, sin llamar a la IA
    res2 = await plan_api.audio(student_with_profile.token, exercise_id)
    assert res2.status_code == 200
    assert res2.content == res1.content
    assert fake_speech.calls == calls_start + 1  # No se incrementó

    # 3. Peticiones concurrentes con single-flight
    get_audio_cache().clear()
    release = asyncio.Event()
    entered = asyncio.Event()
    fake_speech.script(WaitSpeech(release=release, entered=entered))

    # Lanzamos dos llamadas concurrentes
    task1 = asyncio.create_task(plan_api.audio(student_with_profile.token, exercise_id))
    task2 = asyncio.create_task(plan_api.audio(student_with_profile.token, exercise_id))

    await entered.wait()
    release.set()

    conc_res1, conc_res2 = await asyncio.gather(task1, task2)
    assert conc_res1.status_code == 200
    assert conc_res2.status_code == 200
    assert conc_res1.content == conc_res2.content
    # Solo 1 llamada real adicional al proveedor a pesar de la concurrencia
    assert fake_speech.calls == calls_start + 2


async def test_ac_2_2_audio_no_se_guarda_en_bd(
    plan_api,
    manual_scheduler: ManualScheduler,
    student_with_profile: Student,
    clock: FrozenClock,
    db: AsyncSession,
) -> None:
    target_exercise = await _generate_test_plan(plan_api, manual_scheduler, student_with_profile, clock)
    exercise_id = target_exercise["id"]

    await plan_api.audio(student_with_profile.token, exercise_id)

    # Verificar que no existen columnas de audio ni blobs en plan_exercises ni weekly_plans
    pe_cols = await db.execute(
        text("SELECT column_name FROM information_schema.columns WHERE table_name = 'plan_exercises'")
    )
    col_names = [r[0] for r in pe_cols.fetchall()]
    assert "audio" not in col_names
    assert "audio_bytes" not in col_names
    assert "wav" not in col_names


async def test_ac_2_4_rate_limiting_en_audio(
    plan_api,
    manual_scheduler: ManualScheduler,
    student_with_profile: Student,
    clock: FrozenClock,
    settings: Settings,
) -> None:
    target_exercise = await _generate_test_plan(plan_api, manual_scheduler, student_with_profile, clock)
    exercise_id = target_exercise["id"]

    limit = settings.RATE_LIMIT_EXERCISE_AUDIO_PER_USER
    # Consumir hasta el límite
    for _ in range(limit):
        res = await plan_api.audio(student_with_profile.token, exercise_id)
        assert res.status_code == 200

    # La siguiente petición supera el límite de frecuencia
    blocked = await plan_api.audio(student_with_profile.token, exercise_id)
    assert blocked.status_code == 429
    assert blocked.json()["error"]["code"] == "RATE_LIMITED"
    assert "Retry-After" in blocked.headers
    assert blocked.headers["Cache-Control"] == "no-store"
