import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.clock import BOGOTA_TZ, FrozenClock
from app.core.errors import AppError
from app.modules.profile.models import Profile
from app.modules.profile.schemas import DiagnosticProfile
from app.modules.profile.service import ProfileService

NOW = datetime(2026, 10, 12, 10, 0, 0, tzinfo=BOGOTA_TZ)


@pytest.fixture
def clock() -> FrozenClock:
    return FrozenClock(NOW)


@pytest.fixture
def mock_session() -> AsyncMock:
    session = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.flush = AsyncMock()
    return session


@pytest.fixture
def service(mock_session: AsyncMock, clock: FrozenClock) -> ProfileService:
    return ProfileService(mock_session, clock)


async def test_get_diagnostic_retorna_none_si_no_existe_perfil(service: ProfileService) -> None:
    service._repo.get = AsyncMock(return_value=None)

    result = await service.get_diagnostic(uuid.uuid4())
    assert result is None


async def test_update_diagnostic_falla_si_perfil_no_existe(service: ProfileService) -> None:
    service._repo.get = AsyncMock(return_value=None)

    with pytest.raises(AppError) as exc_info:
        await service.update_diagnostic(uuid.uuid4(), {"goal": "strength"})

    assert exc_info.value.status_code == 404
    assert exc_info.value.code == "PROFILE_NOT_FOUND"


async def test_update_diagnostic_falla_si_cuerpo_esta_vacio(service: ProfileService) -> None:
    user_id = uuid.uuid4()
    profile_model = Profile(
        user_id=user_id,
        goal="strength",
        term_weeks=8,
        fitness_level="beginner",
        session_minutes=30,
        has_machine_access=True,
        created_at=NOW,
        updated_at=NOW,
    )
    service._repo.get = AsyncMock(return_value=profile_model)
    service._repo.get_training_days = AsyncMock(return_value=[1, 3, 5])

    with pytest.raises(AppError) as exc_info:
        await service.update_diagnostic(user_id, {})

    assert exc_info.value.status_code == 422
    assert exc_info.value.code == "VALIDATION_ERROR"
    assert any(e.code == "EMPTY_UPDATE" for e in exc_info.value.fields)


async def test_update_diagnostic_falla_con_errores_de_validacion(service: ProfileService) -> None:
    user_id = uuid.uuid4()
    profile_model = Profile(
        user_id=user_id,
        goal="strength",
        term_weeks=8,
        fitness_level="beginner",
        session_minutes=30,
        has_machine_access=True,
        created_at=NOW,
        updated_at=NOW,
    )
    service._repo.get = AsyncMock(return_value=profile_model)
    service._repo.get_training_days = AsyncMock(return_value=[1, 3, 5])

    with pytest.raises(AppError) as exc_info:
        await service.update_diagnostic(user_id, {"goal": "invalid_goal", "training_days": []})

    assert exc_info.value.status_code == 422
    assert exc_info.value.code == "VALIDATION_ERROR"
    field_codes = {e.field: e.code for e in exc_info.value.fields}
    assert field_codes.get("goal") == "INVALID_OPTION"
    assert field_codes.get("training_days") == "DAYS_REQUIRED"


async def test_update_diagnostic_evita_escritura_si_no_hay_cambios(
    service: ProfileService, mock_session: AsyncMock
) -> None:
    user_id = uuid.uuid4()
    profile_model = Profile(
        user_id=user_id,
        goal="strength",
        term_weeks=8,
        fitness_level="beginner",
        session_minutes=30,
        has_machine_access=True,
        created_at=NOW,
        updated_at=NOW,
    )
    service._repo.get = AsyncMock(return_value=profile_model)
    service._repo.get_training_days = AsyncMock(return_value=[1, 3, 5])
    service._repo.update_profile = AsyncMock()

    result = await service.update_diagnostic(user_id, {"goal": "strength", "session_minutes": 30})

    assert result.goal == "strength"
    service._repo.update_profile.assert_not_called()
    mock_session.commit.assert_not_called()


async def test_update_diagnostic_persiste_y_hace_commit_si_hay_cambios(
    service: ProfileService, mock_session: AsyncMock
) -> None:
    user_id = uuid.uuid4()
    profile_model = Profile(
        user_id=user_id,
        goal="strength",
        term_weeks=8,
        fitness_level="beginner",
        session_minutes=30,
        has_machine_access=True,
        created_at=NOW,
        updated_at=NOW,
    )
    # Primera llamada devuelve inicial, segunda llamada devuelve actualizado
    updated_model = Profile(
        user_id=user_id,
        goal="endurance",
        term_weeks=8,
        fitness_level="beginner",
        session_minutes=30,
        has_machine_access=True,
        created_at=NOW,
        updated_at=NOW,
    )
    service._repo.get = AsyncMock(side_effect=[profile_model, updated_model])
    service._repo.get_training_days = AsyncMock(return_value=[1, 3, 5])
    service._repo.update_profile = AsyncMock()

    result = await service.update_diagnostic(user_id, {"goal": "endurance"})

    assert result.goal == "endurance"
    service._repo.update_profile.assert_called_once()
    mock_session.commit.assert_called_once()
