"""FakeTextAdapter: generador determinista para local y pruebas (nunca en producción).

Devuelve un plan VÁLIDO y coherente con la entrada, dimensionado con el mismo estimador de rules.py.
En modo guion, cada llamada consume un comportamiento de la cola (respuesta válida, JSON roto,
JSON incoherente, error del proveedor o espera controlada).
"""
import asyncio
import json
from collections import deque
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from app.ai.errors import AIProviderError, ProviderErrorKind
from app.ai.ports import TextGenerator, TextRequest
from app.ai.use_cases.weekly_plan.rules import (
    MAX_EXERCISES_PER_DAY,
    MIN_EXERCISES_PER_DAY,
    REST_SECONDS_RANGE,
    day_seconds,
    minutes,
)


@dataclass(frozen=True)
class _Exercise:
    name: str
    steps: tuple[str, ...]
    timed: bool = False
    machine: bool = False


BODYWEIGHT: tuple[_Exercise, ...] = (
    _Exercise("Sentadilla con peso corporal", (
        "Separa los pies al ancho de los hombros.",
        "Baja la cadera como si fueras a sentarte en una silla.",
        "Sube empujando el suelo con los talones.",
    )),
    _Exercise("Flexiones de brazos", (
        "Apoya las manos un poco más abiertas que los hombros.",
        "Baja el pecho con el cuerpo en línea recta.",
        "Empuja el suelo hasta extender los brazos.",
    )),
    _Exercise("Zancadas alternas", (
        "Da un paso largo hacia adelante.",
        "Baja hasta que ambas rodillas formen un ángulo recto.",
        "Vuelve al inicio y cambia de pierna.",
    )),
    _Exercise("Plancha frontal", (
        "Apoya los antebrazos y las puntas de los pies.",
        "Mantén el cuerpo en línea recta sin hundir la cadera.",
    ), timed=True),
    _Exercise("Puente de glúteos", (
        "Acuéstate boca arriba con las rodillas flexionadas.",
        "Eleva la cadera apretando los glúteos.",
        "Baja despacio sin apoyar del todo.",
    )),
    _Exercise("Escaladores", (
        "Colócate en posición de plancha alta.",
        "Lleva las rodillas al pecho de forma alterna y rápida.",
    ), timed=True),
    _Exercise("Fondos de tríceps en silla", (
        "Apoya las manos en el borde de una silla firme.",
        "Baja flexionando los codos hacia atrás.",
        "Sube extendiendo los brazos.",
    )),
    _Exercise("Superman", (
        "Acuéstate boca abajo con los brazos extendidos.",
        "Eleva brazos y piernas a la vez.",
        "Sostén un momento y baja despacio.",
    )),
    _Exercise("Sentadilla isométrica en pared", (
        "Apoya la espalda en una pared.",
        "Baja hasta que las rodillas formen un ángulo recto y sostén la posición.",
    ), timed=True),
    _Exercise("Saltos de tijera", (
        "Salta abriendo las piernas y los brazos a la vez.",
        "Vuelve a cerrar con un salto suave.",
    ), timed=True),
    _Exercise("Abdominales cruzados", (
        "Acuéstate boca arriba con las manos detrás de la cabeza.",
        "Lleva el codo hacia la rodilla contraria.",
        "Alterna los lados sin tirar del cuello.",
    )),
    _Exercise("Elevación de talones", (
        "Ponte de pie con los pies al ancho de la cadera.",
        "Sube sobre las puntas de los pies.",
        "Baja despacio hasta apoyar los talones.",
    )),
)

MACHINE: tuple[_Exercise, ...] = (
    _Exercise("Prensa de piernas", (
        "Siéntate con la espalda apoyada y los pies en la plataforma.",
        "Baja la plataforma flexionando las rodillas.",
        "Empuja hasta casi extender las piernas.",
    ), machine=True),
    _Exercise("Jalón al pecho en polea", (
        "Sujeta la barra con las manos más abiertas que los hombros.",
        "Lleva la barra hacia el pecho bajando los codos.",
        "Sube despacio controlando el peso.",
    ), machine=True),
    _Exercise("Remo sentado en polea", (
        "Siéntate con la espalda recta y los pies apoyados.",
        "Lleva el agarre hacia el abdomen juntando los omóplatos.",
        "Extiende los brazos con control.",
    ), machine=True),
    _Exercise("Press de pecho en máquina", (
        "Ajusta el asiento para que los agarres queden a la altura del pecho.",
        "Empuja hacia adelante hasta extender los brazos.",
        "Regresa despacio.",
    ), machine=True),
    _Exercise("Extensión de piernas en máquina", (
        "Siéntate con el rodillo sobre los tobillos.",
        "Extiende las rodillas hasta estirar las piernas.",
        "Baja con control.",
    ), machine=True),
    _Exercise("Curl femoral en máquina", (
        "Acuéstate boca abajo con el rodillo detrás de los tobillos.",
        "Flexiona las rodillas llevando los talones hacia los glúteos.",
        "Vuelve despacio a la posición inicial.",
    ), machine=True),
    _Exercise("Elíptica", (
        "Sube a la máquina y sujeta los agarres.",
        "Pedalea a un ritmo constante manteniendo la espalda recta.",
    ), timed=True, machine=True),
    _Exercise("Aperturas en máquina contractora", (
        "Siéntate con la espalda apoyada y los brazos abiertos.",
        "Junta los brazos al frente del pecho.",
        "Abre despacio sin pasar la línea de los hombros.",
    ), machine=True),
)

DAY_NAMES = {1: "Lunes", 2: "Martes", 3: "Miércoles", 4: "Jueves", 5: "Viernes"}
GOAL_TITLES = {
    "general_health": "salud y movilidad",
    "strength": "fuerza de cuerpo completo",
    "endurance": "resistencia en circuito",
    "weight_loss": "circuito activo",
}
_SETS = {"beginner": 2, "intermediate": 3, "advanced": 4}
_WORK_SECONDS = {"beginner": 20, "intermediate": 30, "advanced": 40}
_REPS = {
    "strength": {"beginner": 10, "intermediate": 8, "advanced": 6},
    "endurance": {"beginner": 12, "intermediate": 15, "advanced": 15},
    "weight_loss": {"beginner": 12, "intermediate": 12, "advanced": 12},
    "general_health": {"beginner": 10, "intermediate": 12, "advanced": 12},
}
_REST = {"strength": 90, "general_health": 60, "weight_loss": 30, "endurance": 30}


def _day_exercises(weekday: int, has_machine_access: bool) -> list[_Exercise]:
    if not has_machine_access:
        pool = list(BODYWEIGHT)
    else:  # alterna máquina y peso corporal
        pool = [ex for pair in zip(MACHINE, BODYWEIGHT, strict=False) for ex in pair]
    offset = (weekday - 1) * 2
    return [pool[(offset + i) % len(pool)] for i in range(MAX_EXERCISES_PER_DAY)]


def build_valid_plan(input_data: Mapping[str, Any]) -> dict[str, Any]:
    """Plan coherente con la entrada; cada día cabe en `session_minutes` según rules.day_seconds."""
    level, goal = input_data["fitness_level"], input_data["goal"]
    budget = input_data["session_minutes"] * 60
    sets, reps, rest = _SETS[level], _REPS[goal][level], _REST[goal]
    work = _WORK_SECONDS[level]

    def shape(exs: list[_Exercise], s: int, r: int, w: int, rest_s: int) -> list[tuple[int, int | None, int | None, int]]:
        return [(s, None, w, rest_s) if ex.timed else (s, r, None, rest_s) for ex in exs]

    days = []
    for weekday in sorted(input_data["training_days"]):
        candidates = _day_exercises(weekday, input_data["has_machine_access"])
        s, r, w, rest_s = sets, reps, work, rest
        # Ajusta descanso, series y repeticiones hasta que quepan al menos 3 ejercicios.
        while day_seconds(shape(candidates[:MIN_EXERCISES_PER_DAY], s, r, w, rest_s)) > budget:
            if rest_s - 15 >= REST_SECONDS_RANGE[0]:
                rest_s -= 15
            elif s > 1:
                s -= 1
            elif r > 5:
                r, w = r - 2, max(10, w - 5)
            else:
                break
        count = MIN_EXERCISES_PER_DAY
        while count < MAX_EXERCISES_PER_DAY and day_seconds(shape(candidates[: count + 1], s, r, w, rest_s)) <= budget:
            count += 1
        chosen = candidates[:count]
        shaped = shape(chosen, s, r, w, rest_s)
        days.append(
            {
                "weekday": weekday,
                "title": f"{DAY_NAMES[weekday]}: {GOAL_TITLES[goal]}",
                "estimated_minutes": minutes(day_seconds(shaped)),
                "exercises": [
                    {
                        "name": ex.name,
                        "sets": sh[0],
                        **({"work_seconds": sh[2]} if ex.timed else {"reps": sh[1]}),
                        "rest_seconds": sh[3],
                        "requires_machine": ex.machine,
                        "steps": list(ex.steps),
                    }
                    for ex, sh in zip(chosen, shaped, strict=True)
                ],
            }
        )
    return {"days": days}


# --- Comportamientos del modo guion ------------------------------------------------------


class Behavior:
    async def apply(self, request: TextRequest) -> str:
        raise NotImplementedError


class Valid(Behavior):
    async def apply(self, request: TextRequest) -> str:
        return json.dumps(build_valid_plan(request.input_data), ensure_ascii=False)


class Raw(Behavior):
    def __init__(self, text: str) -> None:
        self.text = text

    async def apply(self, request: TextRequest) -> str:
        return self.text


class BrokenJson(Raw):
    def __init__(self) -> None:
        super().__init__('{"days": [{"weekday": 1, "title": "Lunes"')


class Incoherent(Behavior):
    """JSON válido con el esquema, pero con un día repetido (viola las reglas)."""

    async def apply(self, request: TextRequest) -> str:
        plan = build_valid_plan(request.input_data)
        plan["days"].append(dict(plan["days"][0]))
        return json.dumps(plan, ensure_ascii=False)


class Fail(Behavior):
    def __init__(self, kind: ProviderErrorKind) -> None:
        self.kind = kind

    async def apply(self, request: TextRequest) -> str:
        raise AIProviderError(self.kind, "simulado")


class Wait(Behavior):
    """Espera controlada: avisa con `entered` y no responde hasta que el test active `release`."""

    def __init__(self, release: asyncio.Event, entered: asyncio.Event | None = None, then: Behavior | None = None):
        self.release, self.entered, self.then = release, entered, then or Valid()

    async def apply(self, request: TextRequest) -> str:
        if self.entered:
            self.entered.set()
        await self.release.wait()
        return await self.then.apply(request)


class Callback(Behavior):
    """Ejecuta `fn` (p. ej. avanzar un reloj falso) y luego delega en `then`."""

    def __init__(self, fn: Callable[[], None], then: Behavior | None = None) -> None:
        self.fn, self.then = fn, then or Valid()

    async def apply(self, request: TextRequest) -> str:
        self.fn()
        return await self.then.apply(request)


class FakeTextAdapter(TextGenerator):
    model_name = "fake"

    def __init__(self) -> None:
        self.requests: list[TextRequest] = []  # espía: todo lo que llegó al puerto
        self._script: deque[Behavior] = deque()

    def script(self, *behaviors: Behavior) -> None:
        self._script.extend(behaviors)

    @property
    def calls(self) -> int:
        return len(self.requests)

    async def generate(self, request: TextRequest) -> str:
        self.requests.append(request)
        behavior = self._script.popleft() if self._script else Valid()
        return await behavior.apply(request)
