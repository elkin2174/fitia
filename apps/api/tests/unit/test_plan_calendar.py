from datetime import date, timedelta

import pytest

from app.modules.plan.calendar import remaining_training_days, target_week, week_days

MONDAY = date(2026, 10, 12)


@pytest.mark.parametrize("offset", range(5))
def test_lunes_a_viernes_usa_la_semana_actual_desde_hoy(offset: int) -> None:
    today = MONDAY + timedelta(days=offset)

    assert target_week(today) == (MONDAY, today)


@pytest.mark.parametrize("offset", [5, 6])
def test_sabado_y_domingo_usan_el_lunes_siguiente(offset: int) -> None:
    next_monday = MONDAY + timedelta(days=7)

    assert target_week(MONDAY + timedelta(days=offset)) == (next_monday, next_monday)


@pytest.mark.parametrize(
    ("offset", "days", "expected"),
    [
        (0, [1, 3, 5], [1, 3, 5]),
        (1, [1, 3, 5], [3, 5]),  # martes: el lunes ya pasó
        (2, [1, 3, 5], [3, 5]),  # miércoles: hoy cuenta
        (4, [1, 2], []),  # viernes con lunes y martes: plan vacío
        (4, [5], [5]),
        (0, [1, 2, 3, 4, 5], [1, 2, 3, 4, 5]),
    ],
)
def test_dias_restantes(offset: int, days: list[int], expected: list[int]) -> None:
    week_start, start_date = target_week(MONDAY + timedelta(days=offset))

    assert remaining_training_days(days, week_start, start_date) == expected


def _statuses(start_offset: int, training: list[int]) -> list[str]:
    start = MONDAY + timedelta(days=start_offset)
    dates = {MONDAY + timedelta(days=d - 1) for d in training}
    return [d.status for d in week_days(MONDAY, start, dates)]


def test_estados_desde_el_lunes() -> None:
    assert _statuses(0, [1, 3, 5]) == ["training", "rest", "training", "rest", "training"]


def test_estados_desde_el_miercoles() -> None:
    assert _statuses(2, [3, 5]) == ["unplanned", "unplanned", "training", "rest", "training"]


def test_siempre_cinco_dias_de_lunes_a_viernes() -> None:
    days = week_days(MONDAY, MONDAY, set())

    assert [d.weekday for d in days] == [1, 2, 3, 4, 5]
    assert [d.date for d in days] == [MONDAY + timedelta(days=i) for i in range(5)]
