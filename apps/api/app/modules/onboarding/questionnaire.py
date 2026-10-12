"""Textos del diagnóstico inicial en español. Los `code` salen SOLO de profile/options.py."""
from app.modules.onboarding.schemas import Question, QuestionnaireResponse, QuestionOption
from app.modules.profile import options

_GOAL_LABELS = {
    "general_health": "Salud general",
    "strength": "Fuerza",
    "endurance": "Resistencia",
    "weight_loss": "Pérdida de peso",
}
_LEVEL_LABELS = {"beginner": "Principiante", "intermediate": "Intermedio", "advanced": "Avanzado"}
_WEEKDAY_LABELS = {1: "Lunes", 2: "Martes", 3: "Miércoles", 4: "Jueves", 5: "Viernes"}
_MACHINE_LABELS = {True: "Sí", False: "No"}


def _question(id_: str, text: str, type_: str, codes: tuple, labels: dict) -> Question:
    # KeyError al importar si options.py gana un valor sin etiqueta: la deriva se detecta de inmediato.
    return Question(
        id=id_,
        text=text,
        type=type_,
        options=[QuestionOption(code=code, label=labels[code]) for code in codes],
    )


QUESTIONNAIRE = QuestionnaireResponse(
    questions=[
        _question("goal", "¿Cuál es tu objetivo principal?", "single", options.GOALS, _GOAL_LABELS),
        _question(
            "term_weeks",
            "¿En cuánto tiempo quieres lograrlo?",
            "single",
            options.TERM_WEEKS,
            {w: f"{w} semanas" for w in options.TERM_WEEKS},
        ),
        _question("fitness_level", "¿Cuál es tu nivel físico actual?", "single", options.FITNESS_LEVELS, _LEVEL_LABELS),
        _question(
            "session_minutes",
            "¿Cuánto tiempo tienes disponible por sesión?",
            "single",
            options.SESSION_MINUTES,
            {m: f"{m} min" for m in options.SESSION_MINUTES},
        ),
        _question(
            "has_machine_access",
            "¿Tienes acceso a máquinas (gimnasio)?",
            "single",
            options.MACHINE_ACCESS,
            _MACHINE_LABELS,
        ),
        _question(
            "training_days",
            "¿Qué días puedes entrenar? Elige uno o más.",
            "multi",
            options.WEEKDAYS,
            _WEEKDAY_LABELS,
        ),
    ]
)
