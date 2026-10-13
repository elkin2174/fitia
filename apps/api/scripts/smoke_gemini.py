"""Prueba manual contra Gemini REAL (NO forma parte del CI).

Genera planes semanales con el gateway de producción (prompt versionado + reglas) y los valida.
No toca la base de datos: las métricas se guardan en memoria.

Uso (desde apps/api):
    GEMINI_API_KEY=... .venv/bin/python -m scripts.smoke_gemini
    GEMINI_API_KEY=... GEMINI_MODEL=gemini-3.5-flash .venv/bin/python -m scripts.smoke_gemini --case beginner
"""
import argparse
import asyncio
import os
import sys

from app.ai.adapters.gemini_text import GeminiTextAdapter
from app.ai.call_log import MemoryCallRecorder
from app.ai.errors import AIFailure
from app.ai.gateway import AIGateway
from app.ai.privacy import WeeklyPlanInput
from app.ai.resilience import CircuitBreaker
from app.ai.use_cases.weekly_plan.use_case import WEEKLY_PLAN
from app.core.clock import Clock
from app.core.config import Settings

CASES: dict[str, WeeklyPlanInput] = {
    "beginner": WeeklyPlanInput(
        goal="general_health", term_weeks=8, fitness_level="beginner", session_minutes=30,
        training_days=[1, 3, 5], has_machine_access=False,
    ),
    "advanced": WeeklyPlanInput(
        goal="strength", term_weeks=12, fitness_level="advanced", session_minutes=60,
        training_days=[1, 2, 3, 4, 5], has_machine_access=True,
    ),
    "short": WeeklyPlanInput(
        goal="weight_loss", term_weeks=4, fitness_level="intermediate", session_minutes=15,
        training_days=[2], has_machine_access=False,
    ),
}


async def run_case(gateway: AIGateway, name: str, plan_input: WeeklyPlanInput) -> bool:
    print(f"\n=== {name}: {plan_input.model_dump()}")
    try:
        result = await gateway.run(WEEKLY_PLAN, plan_input)
    except AIFailure as failure:
        print(f"FALLO {failure.code} ({failure.call_status}) intentos={failure.attempts} {failure.latency_ms} ms")
        return False
    print(f"OK modelo={result.model} intentos={result.attempts} latencia={result.latency_ms} ms")
    for day in result.value.days:
        print(f"  día {day.weekday} · {day.title} · {day.estimated_minutes} min")
        for ex in day.exercises:
            amount = f"{ex.reps} reps" if ex.reps is not None else f"{ex.work_seconds} s"
            machine = " [máquina]" if ex.requires_machine else ""
            print(f"    {ex.position}. {ex.name}: {ex.sets}×{amount}, descanso {ex.rest_seconds} s{machine}")
            for step in ex.steps:
                print(f"       - {step}")
    return True


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", choices=sorted(CASES), action="append")
    args = parser.parse_args()
    if not os.environ.get("GEMINI_API_KEY"):
        print("Define GEMINI_API_KEY", file=sys.stderr)
        return 2

    settings = Settings(_env_file=None, AI_PROVIDER="gemini", AI_ENABLED=True)
    recorder = MemoryCallRecorder()
    gateway = AIGateway(
        settings=settings,
        generator=GeminiTextAdapter(api_key=settings.GEMINI_API_KEY),
        breaker=CircuitBreaker(settings.AI_BREAKER_FAILURES, settings.AI_BREAKER_WINDOW_SECONDS,
                               settings.AI_BREAKER_OPEN_SECONDS),
        recorder=recorder,
        clock=Clock(),
    )
    results = [await run_case(gateway, name, CASES[name]) for name in (args.case or sorted(CASES))]
    print("\nMétricas:", [(e.status, e.attempts, e.latency_ms) for e in recorder.entries])
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
