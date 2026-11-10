"""Caso de uso: Síntesis de voz para ejercicios (MVP 2 - HU 1 y HU 2)."""
from app.ai.use_cases.exercise_audio.builder import build_exercise_audio_text
from app.ai.use_cases.exercise_audio.cache import AudioCache, get_audio_cache, make_cache_key

__all__ = ["build_exercise_audio_text", "AudioCache", "get_audio_cache", "make_cache_key"]
