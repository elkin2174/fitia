"""Pruebas unitarias para el empaquetado de audio PCM a WAV (HU 1)."""
import io
import wave

from app.ai.adapters.gemini_speech import pack_pcm_to_wav


def test_pack_pcm_to_wav_cabecera_y_parametros_validos() -> None:
    sample_rate = 24000
    channels = 1
    sampwidth = 2
    # 0.25 segundos de silencio (6000 muestras * 2 bytes = 12000 bytes)
    num_frames = int(0.25 * sample_rate)
    pcm_data = b"\x00\x00" * num_frames

    wav_bytes = pack_pcm_to_wav(pcm_data, sample_rate=sample_rate, channels=channels, sampwidth=sampwidth)

    assert wav_bytes.startswith(b"RIFF")
    assert b"WAVE" in wav_bytes[:12]

    with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
        assert wf.getnchannels() == channels
        assert wf.getsampwidth() == sampwidth
        assert wf.getframerate() == sample_rate
        assert wf.getnframes() == num_frames
        duration = wf.getnframes() / wf.getframerate()
        assert abs(duration - 0.25) < 0.001
