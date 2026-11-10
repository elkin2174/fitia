"""Pruebas unitarias para la construcción del texto de locución de ejercicios (HU 1)."""
from app.ai.use_cases.exercise_audio.builder import build_exercise_audio_text
from app.modules.plan.models import EXERCISE_DISCLAIMER


def test_build_exercise_audio_text_formato_correcto() -> None:
    name = "Sentadilla con peso corporal"
    steps = [
        "Separa los pies al ancho de los hombros",
        "Baja la cadera como si fueras a sentarte en una silla",
        "Sube empujando el suelo con los talones",
    ]
    disclaimer = EXERCISE_DISCLAIMER

    text = build_exercise_audio_text(name, steps, disclaimer)

    assert text.startswith("Sentadilla con peso corporal.")
    assert "Paso 1: Separa los pies al ancho de los hombros." in text
    assert "Paso 2: Baja la cadera como si fueras a sentarte en una silla." in text
    assert "Paso 3: Sube empujando el suelo con los talones." in text
    assert text.endswith(disclaimer.strip())
    # El disclaimer aparece exactamente una vez
    assert text.count(disclaimer.strip()) == 1


def test_build_exercise_audio_text_no_incluye_identificadores_privados() -> None:
    # Verificación estricta: ningún dato de usuario debe inyectarse en el generador de texto
    user_id = "550e8400-e29b-41d4-a716-446655440000"
    email = "estudiante@correounivalle.edu.co"
    name = "Flexiones de brazos"
    steps = ["Baja el pecho.", "Empuja el suelo."]

    text = build_exercise_audio_text(name, steps, EXERCISE_DISCLAIMER)

    assert user_id not in text
    assert email not in text
    assert "@" not in text


def test_build_exercise_audio_text_ignora_pasos_vacios_y_preserva_puntuacion() -> None:
    name = "Plancha frontal."
    steps = ["  ", "Apoya los antebrazos y pies.", "", "Mantén el cuerpo recto!"]

    text = build_exercise_audio_text(name, steps, EXERCISE_DISCLAIMER)

    assert "Paso 1: Apoya los antebrazos y pies." in text
    assert "Paso 2: Mantén el cuerpo recto!" in text
    assert "Paso 3" not in text
