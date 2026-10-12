import asyncio
import os
import uuid
from collections.abc import AsyncIterator, Callable, Iterator
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx
import pytest
from alembic import command
from alembic.config import Config
from fastapi import Depends
from sqlalchemy import NullPool, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.core.clock import BOGOTA_TZ, FrozenClock, get_clock
from app.core.config import Settings, get_settings
from app.core.db import create_engine, get_session, get_session_factory
from app.core.mailer import get_mailer
from app.core.rate_limit import RateLimiter, get_rate_limiter
from app.core.security import hash_password
from app.modules.auth.cookies import SESSION_COOKIE_NAME
from app.modules.auth.dependencies import CurrentUser, require_complete_profile
from app.modules.auth.models import User
from app.modules.onboarding.status import get_onboarding_status
from app.main import app
from seeds.load_academic_programs import load_programs, read_programs
from app.ai.adapters.fake_text import FakeTextAdapter
from app.ai.call_log import DbCallRecorder
from app.ai.gateway import AIGateway, get_ai_gateway
from app.ai.resilience import CircuitBreaker
from app.modules.plan.runner import get_plan_scheduler
from tests.fakes import FakeMailer, FakeMonotonic, FakeOnboardingStatus, ManualScheduler

API_DIR = Path(__file__).resolve().parents[1]
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/fitia_test"
)
CSRF_HEADERS = {"X-Requested-With": "fitia"}
FRONTEND_URL = "https://fitia.test"


async def _reset_schema() -> None:
    engine = create_engine(TEST_DATABASE_URL, poolclass=NullPool)
    async with engine.begin() as conn:
        await conn.execute(text("DROP SCHEMA public CASCADE"))
        await conn.execute(text("CREATE SCHEMA public"))
    await engine.dispose()


async def _seed() -> None:
    engine = create_engine(TEST_DATABASE_URL, poolclass=NullPool)
    async with engine.begin() as conn:
        await load_programs(conn, read_programs())
    await engine.dispose()


@pytest.fixture(scope="session")
def migrated_database() -> str:
    """Esquema limpio + migraciones reales de Alembic + seed, una vez por sesión de pruebas."""
    asyncio.run(_reset_schema())
    config = Config(str(API_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(API_DIR / "migrations"))
    config.attributes["database_url"] = TEST_DATABASE_URL
    command.upgrade(config, "head")
    asyncio.run(_seed())
    return TEST_DATABASE_URL


@pytest.fixture
async def engine(migrated_database: str) -> AsyncIterator[AsyncEngine]:
    engine = create_engine(migrated_database, poolclass=NullPool)
    yield engine
    async with engine.begin() as conn:
        await conn.execute(text("TRUNCATE users, ai_call_logs CASCADE"))
    await engine.dispose()


@pytest.fixture
def sessionmaker(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


@pytest.fixture
async def db(sessionmaker: async_sessionmaker[AsyncSession]) -> AsyncIterator[AsyncSession]:
    """Sesión para que las pruebas inspeccionen la BD directamente."""
    async with sessionmaker() as session:
        yield session


@pytest.fixture
def clock() -> FrozenClock:
    return FrozenClock(datetime(2026, 10, 12, 9, 0, 0, tzinfo=BOGOTA_TZ))


@pytest.fixture
def mailer() -> FakeMailer:
    return FakeMailer()


@pytest.fixture
def settings() -> Settings:
    return Settings(
        _env_file=None,
        ENV="test",
        FRONTEND_BASE_URL=FRONTEND_URL,
        CONSENT_TEXT_VERSION="2026-01",
        COOKIE_SECURE=True,
        MAIL_PROVIDER="console",
        RATE_LIMIT_PER_IP=30,
        RATE_LIMIT_PER_EMAIL=5,
    )


@pytest.fixture
def fake_ai() -> FakeTextAdapter:
    """Adaptador falso de IA (con cola de comportamientos). `fake_ai.requests` es el espía del puerto."""
    return FakeTextAdapter()


@pytest.fixture
def ai_time() -> FakeMonotonic:
    return FakeMonotonic()


@pytest.fixture
def ai_gateway(
    settings: Settings,
    fake_ai: FakeTextAdapter,
    sessionmaker: async_sessionmaker[AsyncSession],
    clock: FrozenClock,
    ai_time: FakeMonotonic,
) -> AIGateway:
    return AIGateway(
        settings=settings,
        generator=fake_ai,
        breaker=CircuitBreaker(
            settings.AI_BREAKER_FAILURES, settings.AI_BREAKER_WINDOW_SECONDS, settings.AI_BREAKER_OPEN_SECONDS, ai_time
        ),
        recorder=DbCallRecorder(sessionmaker),
        clock=clock,
        time_fn=ai_time,
        sleep=ai_time.sleep,
    )


@pytest.fixture
async def client(
    sessionmaker: async_sessionmaker[AsyncSession],
    clock: FrozenClock,
    mailer: FakeMailer,
    settings: Settings,
    ai_gateway: AIGateway,
) -> AsyncIterator[httpx.AsyncClient]:
    async def _session() -> AsyncIterator[AsyncSession]:
        async with sessionmaker() as session:
            yield session

    limiter = RateLimiter()
    app.dependency_overrides.update(
        {
            get_session: _session,
            get_clock: lambda: clock,
            get_mailer: lambda: mailer,
            get_settings: lambda: settings,
            get_rate_limiter: lambda: limiter,
            get_session_factory: lambda: sessionmaker,
            get_ai_gateway: lambda: ai_gateway,
        }
    )
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test", headers=CSRF_HEADERS) as c:
        yield c
    app.dependency_overrides.clear()


def valid_payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "nickname": "Pantera",
        "email": "ana.gomez@correounivalle.edu.co",
        "password": "contrasena-segura",
        "program_code": "ING-SIS",
        "accepted_terms": True,
    }
    payload.update(overrides)
    return {k: v for k, v in payload.items() if v is not _OMIT}


_OMIT = object()


@pytest.fixture
def omit() -> object:
    """Marcador para quitar un campo del payload: valid_payload(program_code=omit)."""
    return _OMIT


@pytest.fixture
def register(client: httpx.AsyncClient) -> Callable[..., Any]:
    async def _register(**overrides: Any) -> httpx.Response:
        return await client.post("/api/v1/auth/register", json=valid_payload(**overrides))

    return _register


# --- HU 2: usuarios listos para iniciar sesión --------------------------------

PASSWORD = "contrasena-segura"


@dataclass(frozen=True)
class SeededUser:
    id: uuid.UUID
    email: str
    password: str


@pytest.fixture
def make_user(db: AsyncSession, clock: FrozenClock) -> Callable[..., Any]:
    """Inserta un usuario directamente en BD (sin pasar por el registro)."""

    async def _make(
        email: str = "ana.gomez@correounivalle.edu.co",
        *,
        verified: bool = True,
        password: str = PASSWORD,
        password_hash: str | None = None,
        nickname: str = "Pantera",
    ) -> SeededUser:
        user = User(
            email=email,
            password_hash=password_hash or hash_password(password),
            nickname=nickname,
            program_code="ING-SIS",
            created_at=clock.now(),
            email_verified_at=clock.now() if verified else None,
        )
        db.add(user)
        await db.commit()
        return SeededUser(id=user.id, email=email, password=password)

    return _make


@pytest.fixture
async def verified_user(make_user: Callable[..., Any]) -> SeededUser:
    return await make_user()


@pytest.fixture
async def pending_user(make_user: Callable[..., Any]) -> SeededUser:
    return await make_user(verified=False)


@pytest.fixture
def onboarding(client: httpx.AsyncClient) -> FakeOnboardingStatus:
    """Sustituye el puerto OnboardingStatus; por defecto el diagnóstico está incompleto."""
    fake = FakeOnboardingStatus(completed=False)
    app.dependency_overrides[get_onboarding_status] = lambda: fake
    return fake


def session_token(response: httpx.Response) -> str:
    cookie = response.headers["set-cookie"]
    assert cookie.startswith(f"{SESSION_COOKIE_NAME}=")
    return cookie.split(";", 1)[0].split("=", 1)[1]


def with_session(token: str) -> dict[str, str]:
    # El cliente de pruebas usa http, así que la cookie Secure se envía a mano.
    return {"Cookie": f"{SESSION_COOKIE_NAME}={token}"}


@pytest.fixture
def login(client: httpx.AsyncClient) -> Callable[..., Any]:
    async def _login(email: str, password: str = PASSWORD) -> httpx.Response:
        return await client.post("/api/v1/auth/login", json={"email": email, "password": password})

    return _login


# --- HU 3: huella de un usuario en la BD ----------------------------------------


@pytest.fixture
def user_footprint(db: AsyncSession) -> Callable[..., Any]:
    """Cuenta las filas de un usuario en `users` y en TODAS las tablas con `user_id` (catálogo real)."""

    async def _footprint(user_id: uuid.UUID) -> dict[str, int]:
        tables = (
            await db.scalars(
                text(
                    "SELECT table_name FROM information_schema.columns "
                    "WHERE table_schema = 'public' AND column_name = 'user_id' ORDER BY 1"
                )
            )
        ).all()
        counts = {"users": await db.scalar(text("SELECT count(*) FROM users WHERE id = :id"), {"id": user_id}) or 0}
        for table in tables:  # nombres tomados del catálogo, no de entrada externa
            query = text(f'SELECT count(*) FROM "{table}" WHERE user_id = :id')
            counts[table] = await db.scalar(query, {"id": user_id}) or 0
        return counts

    return _footprint


PROTECTED_URL = "/api/v1/__test__/perfil-completo"


@pytest.fixture
def protected_route() -> Iterator[str]:
    """Ruta que solo existe durante la prueba, protegida con el guard S+P (require_complete_profile)."""

    async def _endpoint(user: CurrentUser = Depends(require_complete_profile)) -> dict[str, str]:
        return {"user_id": str(user.id)}

    app.add_api_route(PROTECTED_URL, _endpoint, methods=["GET"])
    route = app.router.routes[-1]
    yield PROTECTED_URL
    app.router.routes.remove(route)


# --- HU 4: diagnóstico inicial ---------------------------------------------------

COMPLETE_URL = "/api/v1/onboarding/complete"
QUESTIONNAIRE_URL = "/api/v1/onboarding/questionnaire"

# Payload válido de referencia (días desordenados a propósito: se guardan ordenados).
VALID_DIAGNOSTIC: dict[str, Any] = {
    "goal": "strength",
    "term_weeks": 8,
    "fitness_level": "beginner",
    "session_minutes": 30,
    "training_days": [5, 1, 3],
    "has_machine_access": True,
}


@dataclass(frozen=True)
class Student:
    """Usuario verificado, con sesión y SIN perfil."""

    user: SeededUser
    token: str


@pytest.fixture
async def student(login: Callable[..., Any], verified_user: SeededUser) -> Student:
    return Student(user=verified_user, token=session_token(await login(verified_user.email)))


@pytest.fixture
def make_student(make_user: Callable[..., Any], login: Callable[..., Any]) -> Callable[..., Any]:
    """Crea estudiantes adicionales (correo distinto) con sesión y sin perfil."""

    async def _make(email: str) -> Student:
        user = await make_user(email)
        return Student(user=user, token=session_token(await login(email)))

    return _make


@pytest.fixture
def complete_diagnostic(client: httpx.AsyncClient) -> Callable[..., Any]:
    """POST /onboarding/complete. `raw` envía bytes tal cual (p. ej. b"null" o b"")."""

    async def _complete(token: str, body: Any = VALID_DIAGNOSTIC, *, raw: bytes | None = None) -> httpx.Response:
        headers = with_session(token)
        if raw is not None:
            return await client.post(
                COMPLETE_URL, content=raw, headers={**headers, "Content-Type": "application/json"}
            )
        return await client.post(COMPLETE_URL, json=body, headers=headers)

    return _complete



# --- HU 5: plan semanal ------------------------------------------------------------

GENERATE_URL = "/api/v1/plan/generate"
CURRENT_URL = "/api/v1/plan/current"


@pytest.fixture
def manual_scheduler(client: httpx.AsyncClient) -> ManualScheduler:
    """La tarea de generación no corre hasta que el test llama a run_next()/run_all()."""
    scheduler = ManualScheduler()
    app.dependency_overrides[get_plan_scheduler] = lambda: scheduler
    return scheduler


@pytest.fixture
async def student_with_profile(student: Student, complete_diagnostic: Callable[..., Any]) -> Student:
    assert (await complete_diagnostic(student.token)).status_code == 201
    return student


@pytest.fixture
def plan_api(client: httpx.AsyncClient) -> Callable[..., Any]:
    """plan_api.generate(token) / plan_api.current(token)."""

    class _PlanApi:
        async def generate(self, token: str, **kwargs: Any) -> httpx.Response:
            return await client.post(GENERATE_URL, headers=with_session(token), **kwargs)

        async def current(self, token: str) -> httpx.Response:
            return await client.get(CURRENT_URL, headers=with_session(token))

    return _PlanApi()


@pytest.fixture
def plan_footprint(db: AsyncSession) -> Callable[..., Any]:
    """Filas del usuario en weekly_plans y, a partir de sus plan_id, en plan_days y plan_exercises."""

    async def _footprint(user_id: uuid.UUID) -> dict[str, int]:
        params = {"id": user_id}
        plans = "SELECT id FROM weekly_plans WHERE user_id = :id"
        return {
            "weekly_plans": await db.scalar(text(f"SELECT count(*) FROM ({plans}) p"), params) or 0,
            "plan_days": await db.scalar(text(f"SELECT count(*) FROM plan_days WHERE plan_id IN ({plans})"), params) or 0,
            "plan_exercises": await db.scalar(
                text(f"SELECT count(*) FROM plan_exercises WHERE plan_id IN ({plans})"), params
            ) or 0,
        }

    return _footprint
