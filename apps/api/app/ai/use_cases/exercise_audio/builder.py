"""Construcción determinista del texto para locución de ejercicios (HU 1 / AC-1-1, AC-1-2, AC-1-3).

Estructura:
"<nombre>. Paso 1: <paso 1>. Paso 2: <paso 2>... <aviso orientativo>"

- El texto se construye en el servidor a partir de los datos del plan (nombre y pasos) y la constante oficial.
- El aviso orientativo se incluye estrictamente una sola vez al final.
- El texto NUNCA incluye identificadores del usuario (user_id, email, nickname, etc.).
"""
from collections.abc import Sequence


def _normalize_sentence(text: str) -> str:
    cleaned = text.strip()
    if not cleaned:
        return ""
    if not cleaned.endswith((".", "!", "?")):
        cleaned += "."
    return cleaned


def build_exercise_audio_text(name: str, steps: Sequence[str], disclaimer: str) -> str:
    """Construye el guion de voz en español para el ejercicio."""
    clean_name = _normalize_sentence(name)

    valid_steps = [s.strip() for s in steps if s and s.strip()]
    formatted_steps: list[str] = []
    for idx, clean_step in enumerate(valid_steps, start=1):
        step_body = clean_step if clean_step.endswith((".", "!", "?")) else f"{clean_step}."
        formatted_steps.append(f"Paso {idx}: {step_body}")

    steps_part = " ".join(formatted_steps)
    clean_disclaimer = disclaimer.strip()

    parts = [clean_name]
    if steps_part:
        parts.append(steps_part)
    if clean_disclaimer:
        parts.append(clean_disclaimer)

    return " ".join(parts).strip()
