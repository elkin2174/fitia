"""Catálogo cerrado de frases fijas de audio (cues) para descansos y modo guiado (MVP 2 - HU 8).

NFR-29: Todo en español: interfaz, errores y voz.
AC-8-3: Solo se aceptan los nombres cerrados de frases; otro nombre devuelve 404 CUE_NOT_FOUND.
"""
from typing import Final

AUDIO_CUES: Final[dict[str, str]] = {
    "descanso": "Descansa y recupera el aliento.",
    "diez-segundos": "Quedan diez segundos.",
    "fin-descanso": "Termina el descanso. ¡A seguir!",
    "fin-rutina": "Terminaste la rutina de hoy. ¡Buen trabajo!",
}


def get_cue_text(name: str) -> str | None:
    """Devuelve el texto en español para la frase fija indicada, o None si no pertenece al catálogo."""
    return AUDIO_CUES.get(name)
