"""Pruebas unitarias de ProfileService para HU7 (perfil, mediciones físicas y ranking)."""
import uuid
from datetime import datetime
from unittest.mock import AsyncMock

import pytest

from app.core.clock import BOGOTA_TZ, FrozenClock
from app.core.errors import AppError
from app.modules.profile.models import PhysicalMeasurement, Profile
from app.modules.profile.schemas import StudentProfile
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


def _sample_profile(user_id: uuid.UUID) -> Profile:
    return Profile(
        user_id=user_id,
        goal="strength",
        term_weeks=8,
        fitness_level="beginner",
        session_minutes=30,
        has_machine_access=True,
        weight_kg=70.0,
        height_cm=175.0,
        physical_updated_at=NOW,
        is_public_ranking=True,
        points=150,
        level=2,
        created_at=NOW,
        updated_at=NOW,
    )


async def test_get_profile_retorna_perfil_completo_con_posicion(service: ProfileService) -> None:
    user_id = uuid.uuid4()
    service._repo.get = AsyncMock(return_value=_sample_profile(user_id))
    service._repo.get_training_days = AsyncMock(return_value=[1, 3, 5])
    service._repo.get_ranking_position = AsyncMock(return_value=3)

    result = await service.get_profile(user_id)

    assert result is not None
    assert isinstance(result, StudentProfile)
    assert result.goal == "strength"
    assert result.weight_kg == 70.0
    assert result.height_cm == 175.0
    assert result.points == 150
    assert result.level == 2
    assert result.ranking_position == 3
    assert result.is_public_ranking is True
    assert result.training_days == [1, 3, 5]


async def test_get_profile_retorna_none_si_no_existe(service: ProfileService) -> None:
    service._repo.get = AsyncMock(return_value=None)
    result = await service.get_profile(uuid.uuid4())
    assert result is None


async def test_update_profile_falla_si_no_existe_perfil(service: ProfileService) -> None:
    service._repo.get = AsyncMock(return_value=None)

    with pytest.raises(AppError) as exc_info:
        await service.update_profile(uuid.uuid4(), {"weight_kg": 75.0})

    assert exc_info.value.status_code == 404
    assert exc_info.value.code == "PROFILE_NOT_FOUND"


async def test_update_profile_falla_si_cuerpo_vacio(service: ProfileService) -> None:
    user_id = uuid.uuid4()
    service._repo.get = AsyncMock(return_value=_sample_profile(user_id))
    service._repo.get_training_days = AsyncMock(return_value=[1, 3, 5])
    service._repo.get_ranking_position = AsyncMock(return_value=1)

    with pytest.raises(AppError) as exc_info:
        await service.update_profile(user_id, {})

    assert exc_info.value.status_code == 422
    assert exc_info.value.code == "VALIDATION_ERROR"
    assert any(e.code == "EMPTY_UPDATE" for e in exc_info.value.fields)


async def test_update_profile_rechaza_campos_no_editables(service: ProfileService) -> None:
    user_id = uuid.uuid4()
    service._repo.get = AsyncMock(return_value=_sample_profile(user_id))
    service._repo.get_training_days = AsyncMock(return_value=[1, 3, 5])
    service._repo.get_ranking_position = AsyncMock(return_value=1)

    with pytest.raises(AppError) as exc_info:
        await service.update_profile(user_id, {"points": 9999, "level": 10})

    assert exc_info.value.status_code == 422
    assert exc_info.value.code == "VALIDATION_ERROR"
    codes = {e.field: e.code for e in exc_info.value.fields}
    assert codes.get("points") == "NOT_EDITABLE"
    assert codes.get("level") == "NOT_EDITABLE"


async def test_update_profile_evita_escritura_si_valores_son_identicos(
    service: ProfileService, mock_session: AsyncMock
) -> None:
    user_id = uuid.uuid4()
    service._repo.get = AsyncMock(return_value=_sample_profile(user_id))
    service._repo.get_training_days = AsyncMock(return_value=[1, 3, 5])
    service._repo.get_ranking_position = AsyncMock(return_value=1)
    service._repo.update_profile = AsyncMock()

    result = await service.update_profile(user_id, {"weight_kg": 70.0, "is_public_ranking": True})

    assert result.weight_kg == 70.0
    service._repo.update_profile.assert_not_called()
    mock_session.commit.assert_not_called()


async def test_update_profile_agrega_medicion_fisica_al_cambiar_peso(
    service: ProfileService, mock_session: AsyncMock
) -> None:
    user_id = uuid.uuid4()
    initial = _sample_profile(user_id)
    updated = _sample_profile(user_id)
    updated.weight_kg = 75.0

    service._repo.get = AsyncMock(side_effect=[initial, updated])
    service._repo.get_training_days = AsyncMock(return_value=[1, 3, 5])
    service._repo.get_ranking_position = AsyncMock(return_value=1)
    service._repo.update_profile = AsyncMock()
    service._repo.add_physical_measurement = AsyncMock()

    result = await service.update_profile(user_id, {"weight_kg": 75.0})

    assert result.weight_kg == 75.0
    service._repo.add_physical_measurement.assert_called_once()
    saved_m = service._repo.add_physical_measurement.call_args[0][0]
    assert isinstance(saved_m, PhysicalMeasurement)
    assert saved_m.weight_kg == 75.0
    assert saved_m.height_cm == 175.0
    mock_session.commit.assert_called_once()


async def test_update_profile_no_agrega_medicion_fisica_si_solo_cambia_diagnostico(
    service: ProfileService, mock_session: AsyncMock
) -> None:
    user_id = uuid.uuid4()
    initial = _sample_profile(user_id)
    updated = _sample_profile(user_id)
    updated.goal = "endurance"

    service._repo.get = AsyncMock(side_effect=[initial, updated])
    service._repo.get_training_days = AsyncMock(return_value=[1, 3, 5])
    service._repo.get_ranking_position = AsyncMock(return_value=1)
    service._repo.update_profile = AsyncMock()
    service._repo.add_physical_measurement = AsyncMock()

    result = await service.update_profile(user_id, {"goal": "endurance"})

    assert result.goal == "endurance"
    service._repo.add_physical_measurement.assert_not_called()
    service._repo.update_profile.assert_called_once()
    mock_session.commit.assert_called_once()


async def test_update_profile_hace_rollback_si_falla_persistencia(
    service: ProfileService, mock_session: AsyncMock
) -> None:
    user_id = uuid.uuid4()
    service._repo.get = AsyncMock(return_value=_sample_profile(user_id))
    service._repo.get_training_days = AsyncMock(return_value=[1, 3, 5])
    service._repo.get_ranking_position = AsyncMock(return_value=1)
    service._repo.update_profile = AsyncMock(side_effect=RuntimeError("db error"))

    with pytest.raises(RuntimeError):
        await service.update_profile(user_id, {"goal": "endurance"})

    mock_session.rollback.assert_called_once()


async def test_get_public_ranking_mapea_resultados_correctamente(service: ProfileService) -> None:
    service._repo.get_public_ranking = AsyncMock(return_value=[(1, "Ana", 200, 3), (2, "Carlos", 150, 2)])

    items = await service.get_public_ranking(limit=10)

    assert len(items) == 2
    assert items[0].position == 1
    assert items[0].nickname == "Ana"
    assert items[0].points == 200
    assert items[0].level == 3
    assert items[1].position == 2
    assert items[1].nickname == "Carlos"
