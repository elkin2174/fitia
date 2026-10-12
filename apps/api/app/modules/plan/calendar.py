"""Calendario del plan (funciones puras; la fecha de hoy la da el Clock en America/Bogota)."""
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Literal

DayStatus = Literal["training", "rest", "unplanned", "completed"]  # "completed" llega con las Épicas 4-5
WEEKDAYS = (1, 2, 3, 4, 5)


@dataclass(frozen=True)
class CalendarDay:
    date: date
    weekday: int  # 1 = lunes … 5 = viernes
    status: DayStatus


def target_week(today: date) -> tuple[date, date]:
    """(week_start, start_date). Lunes a viernes: la semana actual desde hoy. Sábado o domingo: el lunes siguiente."""
    weekday = today.isoweekday()
    if weekday <= 5:
        return today - timedelta(days=weekday - 1), today
    next_monday = today + timedelta(days=8 - weekday)
    return next_monday, next_monday


def date_for(week_start: date, weekday: int) -> date:
    return week_start + timedelta(days=weekday - 1)


def remaining_training_days(training_days: list[int], week_start: date, start_date: date) -> list[int]:
    """Días elegidos cuya fecha es >= start_date (los anteriores de esta semana ya pasaron)."""
    return [d for d in sorted(training_days) if date_for(week_start, d) >= start_date]


def week_days(week_start: date, start_date: date, training_dates: set[date]) -> list[CalendarDay]:
    """Los 5 días de lunes a viernes: training (hay rutina), rest (sin rutina) o unplanned (antes del inicio)."""
    days = []
    for weekday in WEEKDAYS:
        day = date_for(week_start, weekday)
        if day in training_dates:
            status: DayStatus = "training"
        elif day >= start_date:
            status = "rest"
        else:
            status = "unplanned"
        days.append(CalendarDay(date=day, weekday=weekday, status=status))
    return days
