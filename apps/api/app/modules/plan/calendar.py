"""Calendario del plan (funciones puras; la fecha de hoy la da el Clock en America/Bogota)."""
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Literal, Protocol

DayStatus = Literal["training", "rest", "unplanned", "completed"]  # "completed" llega con las Épicas 4-5
WEEKDAYS = (1, 2, 3, 4, 5)


class TrainingDayLike(Protocol):
    plan_date: date
    title: str


@dataclass(frozen=True)
class CalendarDay:
    date: date
    weekday: int  # 1 = lunes … 5 = viernes
    status: DayStatus


@dataclass(frozen=True)
class NextTrainingDayView:
    date: date
    weekday: int
    title: str | None
    planned: bool


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


def find_next_training_day(
    today: date,
    target_week_start: date,
    current_plan_days: list[TrainingDayLike] | None,
    next_week_plan_days: list[TrainingDayLike] | None,
    profile_training_weekdays: list[int],
) -> NextTrainingDayView | None:
    """Calcula el próximo día de entrenamiento para un día de descanso o fin de semana.

    - Entre semana: busca el siguiente día en el plan vigente con fecha posterior a hoy.
      Si no queda ninguno en la semana, busca en la semana siguiente (plan vigente o días del perfil).
    - Fin de semana: target_week_start ya es el lunes siguiente; busca el primer día del plan
      de la semana siguiente si existe; si no, el primer día de training_days del perfil (planned=False).
    """
    weekday = today.isoweekday()
    if weekday <= 5:
        if current_plan_days:
            future = [d for d in current_plan_days if d.plan_date > today]
            if future:
                earliest = min(future, key=lambda d: d.plan_date)
                return NextTrainingDayView(
                    date=earliest.plan_date,
                    weekday=earliest.plan_date.isoweekday(),
                    title=earliest.title,
                    planned=True,
                )
        next_week_start = target_week_start + timedelta(days=7)
        if next_week_plan_days:
            earliest = min(next_week_plan_days, key=lambda d: d.plan_date)
            return NextTrainingDayView(
                date=earliest.plan_date,
                weekday=earliest.plan_date.isoweekday(),
                title=earliest.title,
                planned=True,
            )
        if profile_training_weekdays:
            first_wd = min(profile_training_weekdays)
            first_date = date_for(next_week_start, first_wd)
            return NextTrainingDayView(
                date=first_date,
                weekday=first_wd,
                title=None,
                planned=False,
            )
        return None
    else:
        next_week_start = target_week_start
        if current_plan_days:
            earliest = min(current_plan_days, key=lambda d: d.plan_date)
            return NextTrainingDayView(
                date=earliest.plan_date,
                weekday=earliest.plan_date.isoweekday(),
                title=earliest.title,
                planned=True,
            )
        if profile_training_weekdays:
            first_wd = min(profile_training_weekdays)
            first_date = date_for(next_week_start, first_wd)
            return NextTrainingDayView(
                date=first_date,
                weekday=first_wd,
                title=None,
                planned=False,
            )
        return None
