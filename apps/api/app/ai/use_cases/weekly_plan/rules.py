"""Reglas deterministas del plan semanal (NFR-17, NFR-18). Constantes en un solo lugar.

Cualquier violación → AIInvalidOutput: el plan completo se descarta.
"""
import math
import re
import unicodedata
from dataclasses import dataclass

from app.ai.errors import AIInvalidOutput
from app.ai.privacy import WeeklyPlanInput
from app.ai.use_cases.weekly_plan.schema import ExerciseOut, WeeklyPlanOutput

# --- Límites (la migración 0003 replica los rangos en CHECK) -------------------------------
MIN_EXERCISES_PER_DAY = 3
MAX_EXERCISES_PER_DAY = 8
SETS_RANGE = (1, 6)
REPS_RANGE = (1, 30)
WORK_SECONDS_RANGE = (10, 120)
REST_SECONDS_RANGE = (15, 180)
STEPS_RANGE = (2, 4)
STEP_MAX_CHARS = 200
TITLE_MAX_CHARS = 60
NAME_MAX_CHARS = 80
BEGINNER_MAX_SETS = 4
BEGINNER_MAX_REPS = 20

# --- Estimador de duración (lo usan el servidor y el adaptador falso) -------------------
SECONDS_PER_REP = 3
TRANSITION_SECONDS = 30

# --- Listas de términos (comparación sin tildes, en minúsculas y por palabra completa) ----
MACHINE_TERMS: tuple[str, ...] = (
    "maquina", "maquinas", "prensa", "polea", "poleas", "smith", "jalon", "jalones", "contractora",
    "eliptica", "caminadora", "trotadora", "cinta de correr", "bicicleta estatica", "remo ergometro",
    "multifuerza", "multiestacion", "peck deck", "hack squat", "cable", "cables",
    # Sin acceso a máquinas el plan es solo de peso corporal: tampoco pesos libres.
    "mancuerna", "mancuernas", "barra olimpica", "kettlebell", "pesa rusa", "disco de peso",
)
FORBIDDEN_TERMS: tuple[str, ...] = (
    "dieta", "dietas", "nutricion", "nutricional", "suplemento", "suplementos", "suplementacion",
    "medicamento", "medicamentos", "farmaco", "farmacos", "caloria", "calorias", "diagnostico",
    "esteroide", "esteroides", "anabolico", "anabolicos", "proteina", "proteinas", "creatina",
    "ayuno", "receta", "dosis",
)
ENGLISH_STOPWORDS = frozenset(
    "the and with your you for of to on in keep back hold push pull slowly then each this that is are".split()
)
SPANISH_STOPWORDS = frozenset(
    "el la los las de del y con tu en para por un una al se lo que es manten mantén baja sube hasta".split()
)

_URL_RE = re.compile(r"https?://|www\.|\b[a-z0-9-]+\.(?:com|org|net|io|co|edu|gov)\b", re.IGNORECASE)
_HTML_RE = re.compile(r"<\s*/?\s*[a-zA-Z!][^>]*>")
_WORD_RE = re.compile(r"[a-z0-9ñ]+")


def normalize(text: str) -> str:
    """Minúsculas y sin tildes (la ñ se conserva)."""
    decomposed = unicodedata.normalize("NFD", text.lower().replace("ñ", "\x00"))
    stripped = "".join(c for c in decomposed if unicodedata.category(c) != "Mn")
    return stripped.replace("\x00", "ñ")


def words(text: str) -> list[str]:
    return _WORD_RE.findall(normalize(text))


def contains_term(text: str, terms: tuple[str, ...]) -> str | None:
    """Primer término presente como palabra(s) completa(s), o None."""
    padded = f" {' '.join(words(text))} "
    return next((term for term in terms if f" {term} " in padded), None)


def exercise_seconds(sets: int, reps: int | None, work_seconds: int | None, rest_seconds: int) -> int:
    work = work_seconds if work_seconds is not None else (reps or 0) * SECONDS_PER_REP
    return sets * work + (sets - 1) * rest_seconds


def day_seconds(exercises: list[tuple[int, int | None, int | None, int]]) -> int:
    """`exercises`: (sets, reps, work_seconds, rest_seconds). Incluye 30 s de transición entre ejercicios."""
    total = sum(exercise_seconds(*e) for e in exercises)
    return total + TRANSITION_SECONDS * max(0, len(exercises) - 1)


def minutes(seconds: int) -> int:
    return math.ceil(seconds / 60)


@dataclass(frozen=True)
class ValidatedExercise:
    position: int
    name: str
    sets: int
    reps: int | None
    work_seconds: int | None
    rest_seconds: int
    requires_machine: bool
    steps: tuple[str, ...]


@dataclass(frozen=True)
class ValidatedDay:
    weekday: int
    title: str
    estimated_minutes: int  # calculado por el servidor
    exercises: tuple[ValidatedExercise, ...]


@dataclass(frozen=True)
class ValidatedPlan:
    days: tuple[ValidatedDay, ...]


def _fail(reason: str) -> AIInvalidOutput:
    return AIInvalidOutput(reason)


def _in_range(value: int, bounds: tuple[int, int]) -> bool:
    return bounds[0] <= value <= bounds[1]


def _check_text(text: str, where: str, *, allow_machines: bool) -> None:
    if _URL_RE.search(text):
        raise _fail(f"{where}: contiene una URL")
    if _HTML_RE.search(text):
        raise _fail(f"{where}: contiene HTML")
    if term := contains_term(text, FORBIDDEN_TERMS):
        raise _fail(f"{where}: término de dieta o consejo médico ({term})")
    if not allow_machines and (term := contains_term(text, MACHINE_TERMS)):
        raise _fail(f"{where}: menciona equipamiento sin acceso a máquinas ({term})")


def _check_exercise(ex: ExerciseOut, where: str, plan_input: WeeklyPlanInput) -> None:
    if not ex.name.strip() or len(ex.name.strip()) > NAME_MAX_CHARS:
        raise _fail(f"{where}: nombre vacío o demasiado largo")
    if not _in_range(ex.sets, SETS_RANGE):
        raise _fail(f"{where}: series fuera de rango")
    if (ex.reps is None) == (ex.work_seconds is None):
        raise _fail(f"{where}: debe tener exactamente uno entre repeticiones y segundos de trabajo")
    if ex.reps is not None and not _in_range(ex.reps, REPS_RANGE):
        raise _fail(f"{where}: repeticiones fuera de rango")
    if ex.work_seconds is not None and not _in_range(ex.work_seconds, WORK_SECONDS_RANGE):
        raise _fail(f"{where}: segundos de trabajo fuera de rango")
    if not _in_range(ex.rest_seconds, REST_SECONDS_RANGE):
        raise _fail(f"{where}: descanso fuera de rango")
    if plan_input.fitness_level == "beginner" and (
        ex.sets > BEGINNER_MAX_SETS or (ex.reps is not None and ex.reps > BEGINNER_MAX_REPS)
    ):
        raise _fail(f"{where}: excede el tope para principiantes")
    if not _in_range(len(ex.steps), STEPS_RANGE):
        raise _fail(f"{where}: la explicación debe tener de 2 a 4 pasos")
    for step in ex.steps:
        if not step.strip() or len(step) > STEP_MAX_CHARS:
            raise _fail(f"{where}: paso vacío o de más de {STEP_MAX_CHARS} caracteres")
    if ex.requires_machine and not plan_input.has_machine_access:
        raise _fail(f"{where}: requiere máquina sin acceso a máquinas")
    for text in (ex.name, *ex.steps):
        _check_text(text, where, allow_machines=plan_input.has_machine_access)
    _check_language(" ".join((ex.name, *ex.steps)), where)


def _check_language(text: str, where: str) -> None:
    """Heurística ligera: se rechaza si predominan las palabras vacías del inglés."""
    tokens = words(text)
    english = sum(t in ENGLISH_STOPWORDS for t in tokens)
    spanish = sum(t in SPANISH_STOPWORDS for t in tokens)
    if english >= 3 and english > spanish:
        raise _fail(f"{where}: el texto no está en español")


def validate_weekly_plan(output: WeeklyPlanOutput, plan_input: WeeklyPlanInput) -> ValidatedPlan:
    weekdays = [d.weekday for d in output.days]
    if len(weekdays) != len(set(weekdays)):
        raise _fail("días repetidos")
    if sorted(weekdays) != sorted(plan_input.training_days):
        raise _fail("los días no coinciden con los días de entrenamiento")

    budget = plan_input.session_minutes * 60
    days: list[ValidatedDay] = []
    for day in sorted(output.days, key=lambda d: d.weekday):
        where = f"día {day.weekday}"
        title = day.title.strip()
        if not title or len(title) > TITLE_MAX_CHARS:
            raise _fail(f"{where}: título vacío o de más de {TITLE_MAX_CHARS} caracteres")
        _check_text(title, where, allow_machines=plan_input.has_machine_access)
        if not MIN_EXERCISES_PER_DAY <= len(day.exercises) <= MAX_EXERCISES_PER_DAY:
            raise _fail(f"{where}: debe tener de {MIN_EXERCISES_PER_DAY} a {MAX_EXERCISES_PER_DAY} ejercicios")
        names = [normalize(ex.name.strip()) for ex in day.exercises]
        if len(names) != len(set(names)):
            raise _fail(f"{where}: ejercicios repetidos")
        for index, ex in enumerate(day.exercises, start=1):
            _check_exercise(ex, f"{where}, ejercicio {index}", plan_input)

        seconds = day_seconds([(e.sets, e.reps, e.work_seconds, e.rest_seconds) for e in day.exercises])
        if seconds > budget:
            raise _fail(f"{where}: la sesión dura {minutes(seconds)} min y el máximo es {plan_input.session_minutes}")

        days.append(
            ValidatedDay(
                weekday=day.weekday,
                title=title,
                estimated_minutes=minutes(seconds),
                exercises=tuple(
                    ValidatedExercise(
                        position=i,
                        name=ex.name.strip(),
                        sets=ex.sets,
                        reps=ex.reps,
                        work_seconds=ex.work_seconds,
                        rest_seconds=ex.rest_seconds,
                        requires_machine=ex.requires_machine,
                        steps=tuple(s.strip() for s in ex.steps),
                    )
                    for i, ex in enumerate(day.exercises, start=1)
                ),
            )
        )
    return ValidatedPlan(days=tuple(days))
