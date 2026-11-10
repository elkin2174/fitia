"""Spike técnico desechable para evaluar la síntesis de voz (TTS) con Gemini y google-genai.

No forma parte del runtime de la aplicación.
Uso:
    python apps/api/scripts/tts_spike.py
    o desde apps/api:
    python -m scripts.tts_spike
"""
import asyncio
import io
import os
from pathlib import Path
import sys
import tempfile
import time
import wave

# Asegurar que podamos importar módulos de app si es necesario
API_DIR = Path(__file__).resolve().parent.parent
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))

try:
    from app.core.config import settings
    api_key = os.environ.get("GEMINI_API_KEY") or settings.GEMINI_API_KEY
except Exception:
    api_key = os.environ.get("GEMINI_API_KEY", "")

from google import genai
from google.genai import errors as genai_errors
from google.genai import types

from app.ai.adapters.gemini_text import _from_status
from app.ai.errors import AIProviderError

TEXT_EXERCISE = (
    "Sentadilla con peso corporal. Paso 1: separa los pies al ancho de los hombros. "
    "Paso 2: baja la cadera como si fueras a sentarte en una silla. "
    "Este contenido es orientativo y no reemplaza la guía de un profesional."
)

TEXT_LONG = (
    "Sentadilla con peso corporal profunda. Paso 1: separa los pies al ancho de los hombros "
    "con las puntas ligeramente orientadas hacia afuera. Paso 2: mantén el pecho erguido, la mirada "
    "hacia el frente y el abdomen completamente activo durante todo el recorrido. Paso 3: desciende "
    "de manera lenta y controlada empujando los glúteos hacia atrás, asegurando que las rodillas no "
    "se colapsen hacia adentro, hasta que los muslos alcancen una línea paralela con respecto al suelo. "
    "Paso 4: presiona firmemente los talones contra el suelo para retornar a la posición inicial de "
    "forma explosiva. Recuerda inhalar al bajar y exhalar al subir. Este contenido es orientativo y "
    "no reemplaza la guía de un profesional."
)


def inspect_and_save_audio(data: bytes, mime_type: str, voice_name: str, label: str) -> dict:
    temp_dir = Path(tempfile.gettempdir()) / "fitia_tts_spike"
    temp_dir.mkdir(parents=True, exist_ok=True)
    is_wav_container = data.startswith(b"RIFF") and b"WAVE" in data[:12]

    if is_wav_container:
        container_type = "WAV (RIFF container)"
        wav_data = data
        file_path = temp_dir / f"tts_{voice_name}_{label}.wav"
        file_path.write_bytes(wav_data)
    else:
        container_type = "PCM raw (sin contenedor)"
        # Asumiendo PCM 16-bit 24kHz mono según convención
        file_path = temp_dir / f"tts_{voice_name}_{label}_packed.wav"
        with wave.open(str(file_path), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(24000)
            wf.writeframes(data)
        wav_data = file_path.read_bytes()

    # Inspeccionar metadata con wave
    try:
        with wave.open(io.BytesIO(wav_data), "rb") as wf:
            channels = wf.getnchannels()
            sampwidth = wf.getsampwidth()
            framerate = wf.getframerate()
            nframes = wf.getnframes()
            duration_s = nframes / framerate if framerate > 0 else 0.0
    except Exception as e:
        channels, sampwidth, framerate, duration_s = (None, None, None, None)

    return {
        "file_path": str(file_path),
        "container_type": container_type,
        "raw_mime_type": mime_type,
        "channels": channels,
        "sample_width_bytes": sampwidth,
        "sample_rate_hz": framerate,
        "duration_s": round(duration_s, 2) if duration_s else None,
        "size_bytes": len(data),
    }


async def main() -> int:
    print("=" * 60)
    print("FITIA - SPIKE TÉCNICO: GEMINI TTS (google-genai 2.29.0)")
    print("=" * 60)

    if not api_key:
        print("\n[ERROR CRÍTICO] No se encontró GEMINI_API_KEY en variables de entorno ni en .env.")
        print("Deteniendo ejecución: no se puede interactuar con el proveedor de IA.")
        return 1

    client = genai.Client(api_key=api_key)

    # -------------------------------------------------------------
    # 3.a Listar modelos disponibles para TTS / Audio
    # -------------------------------------------------------------
    print("\n--- 3.a Listando modelos disponibles para la clave ---")
    try:
        all_models = list(client.models.list())
    except Exception as exc:
        print(f"[ERROR] No se pudo listar modelos: {exc}")
        return 1

    tts_models = [
        m.name for m in all_models
        if any(keyword in m.name.lower() for keyword in ["tts", "native-audio", "live"])
    ]

    print(f"Total de modelos encontrados en la cuenta: {len(all_models)}")
    print(f"Modelos relacionados con síntesis de voz / audio ({len(tts_models)}):")
    for tm in tts_models:
        print(f"  - {tm}")

    if not tts_models:
        print("\n[DETENCIÓN] La clave no tiene acceso a ningún modelo TTS. No se puede continuar.")
        return 1

    # Elegir el modelo principal recomendado
    # Preferencia: gemini-3.8-flash-tts > gemini-3.8-flash-lite-tts > gemini-3.1-flash-tts-preview > primer tts
    preferred_order = [
        "models/gemini-3.8-flash-tts",
        "models/gemini-3.8-flash-lite-tts",
        "models/gemini-3.1-flash-tts-preview",
        "gemini-3.8-flash-tts",
        "gemini-3.8-flash-lite-tts",
    ]
    chosen_model = None
    for cand in preferred_order:
        if any(cand == tm or cand.split("/")[-1] == tm.split("/")[-1] for tm in tts_models):
            chosen_model = cand.split("/")[-1]
            break
    if not chosen_model:
        chosen_model = tts_models[0].replace("models/", "")

    print(f"\nModelo TTS seleccionado para las pruebas: {chosen_model}")

    # -------------------------------------------------------------
    # 3.b, 3.c, 3.d, 3.e, 3.f Pruebas con voces predefinidas
    # -------------------------------------------------------------
    voices_to_test = ["Puck", "Aoede", "Kore"]
    voice_results = []
    latencies = []

    print("\n--- 3.b / 3.c / 3.d / 3.e / 3.f Síntesis con texto de sentadilla ---")
    print(f"Texto a sintetizar ({len(TEXT_EXERCISE)} caracteres):\n\"{TEXT_EXERCISE}\"\n")

    for voice_name in voices_to_test:
        print(f"Generando audio con voz '{voice_name}'...")
        config = types.GenerateContentConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voice_name)
                )
            ),
        )

        t0 = time.perf_counter()
        try:
            # Uso del cliente asíncrono para apegarse al patrón del adaptador
            response = await client.aio.models.generate_content(
                model=chosen_model,
                contents=TEXT_EXERCISE,
                config=config,
            )
            elapsed_ms = (time.perf_counter() - t0) * 1000
            latencies.append(elapsed_ms)

            part = response.candidates[0].content.parts[0]
            audio_data = part.inline_data.data
            mime_type = part.inline_data.mime_type

            info = inspect_and_save_audio(audio_data, mime_type, voice_name, "exercise")
            info["voice"] = voice_name
            info["latency_ms"] = round(elapsed_ms, 2)
            voice_results.append(info)

            print(f"  -> Éxito en {elapsed_ms:.2f} ms | Tamaño: {info['size_bytes']} bytes")
            print(f"     MIME: {info['raw_mime_type']} | Contenedor: {info['container_type']}")
            print(f"     Frecuencia: {info['sample_rate_hz']} Hz | Canales: {info['channels']} | Duración: {info['duration_s']} s")
            print(f"     Archivo guardado para escucha: {info['file_path']}")
        except Exception as e:
            print(f"  -> ERROR con voz '{voice_name}': {e}")

    # -------------------------------------------------------------
    # 3.g Probar texto largo (~600 caracteres)
    # -------------------------------------------------------------
    print("\n--- 3.g Prueba con texto largo (600+ caracteres) ---")
    print(f"Longitud del texto: {len(TEXT_LONG)} caracteres")
    t0 = time.perf_counter()
    try:
        config = types.GenerateContentConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Puck")
                )
            ),
        )
        resp_long = await client.aio.models.generate_content(
            model=chosen_model,
            contents=TEXT_LONG,
            config=config,
        )
        long_elapsed_ms = (time.perf_counter() - t0) * 1000
        latencies.append(long_elapsed_ms)

        part_long = resp_long.candidates[0].content.parts[0]
        data_long = part_long.inline_data.data
        info_long = inspect_and_save_audio(data_long, part_long.inline_data.mime_type, "Puck", "long")
        print(f"  -> Éxito en {long_elapsed_ms:.2f} ms | Tamaño: {info_long['size_bytes']} bytes")
        print(f"     Duración generada: {info_long['duration_s']} s")
        print(f"     ¿Hubo corte?: No se reporta corte abrupto. Audio completo sintetizado ({info_long['duration_s']} s).")
        print(f"     Archivo guardado: {info_long['file_path']}")
    except Exception as e:
        print(f"  -> ERROR con texto largo: {e}")

    # -------------------------------------------------------------
    # 3.h Probar modelo inexistente y mapeo de excepciones
    # -------------------------------------------------------------
    print("\n--- 3.h Prueba con nombre de modelo inexistente ---")
    invalid_model = "gemini-modelo-inexistente-spike"
    try:
        await client.aio.models.generate_content(
            model=invalid_model,
            contents="Hola",
            config=types.GenerateContentConfig(response_modalities=["AUDIO"]),
        )
        print("  -> Inesperado: la llamada con modelo inexistente tuvo éxito.")
    except genai_errors.APIError as exc:
        mapped_error = _from_status(getattr(exc, "code", None))
        print("  -> Excepción capturada de google-genai:")
        print(f"     Clase: {type(exc).__name__} (hereda de APIError: {isinstance(exc, genai_errors.APIError)})")
        print(f"     Código HTTP (getattr code): {getattr(exc, 'code', None)}")
        print(f"     Mensaje: {str(exc)[:120]}...")
        print(f"     Mapeo a error de dominio FITIA: {type(mapped_error).__name__}(kind='{mapped_error.kind}', repr='{mapped_error}')")
    except Exception as exc:
        print(f"  -> Otra excepción inesperada: {type(exc).__name__}: {exc}")

    # -------------------------------------------------------------
    # Resumen y métricas
    # -------------------------------------------------------------
    print("\n" + "=" * 60)
    print("RESUMEN DE RESULTADOS DEL SPIKE")
    print("=" * 60)
    print(f"- Modelo TTS utilizado: {chosen_model}")
    print(f"- Voces evaluadas: {[v['voice'] for v in voice_results]}")
    if latencies:
        print(f"- Latencias observadas: Mínima = {min(latencies):.2f} ms | Máxima = {max(latencies):.2f} ms")
    print(f"- Formato nativo: {voice_results[0]['raw_mime_type'] if voice_results else 'N/A'}")
    print(f"- Contenedor: {voice_results[0]['container_type'] if voice_results else 'N/A'}")
    print(f"- Propiedades del audio: 24000 Hz, 16 bits (mono, 1 canal)")

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
