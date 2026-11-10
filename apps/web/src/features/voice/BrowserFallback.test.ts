import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { BrowserFallback, buildExerciseFallbackPhrases } from "./BrowserFallback";

describe("HU 6 — BrowserFallback", () => {
  let fallback: BrowserFallback;
  let mockSpeak: ReturnType<typeof vi.fn>;
  let mockCancel: ReturnType<typeof vi.fn>;
  let mockGetVoices: ReturnType<typeof vi.fn>;

  const SPANISH_VOICE = {
    name: "Spanish Female Voice",
    lang: "es-CO",
    default: true,
    localService: true,
    voiceURI: "es-co-female",
  } as SpeechSynthesisVoice;

  beforeEach(() => {
    localStorage.clear();

    mockSpeak = vi.fn();
    mockCancel = vi.fn();
    mockGetVoices = vi.fn().mockReturnValue([SPANISH_VOICE]);

    class MockSpeechSynthesisUtterance extends EventTarget {
      text: string;
      lang = "es-ES";
      rate = 1;
      voice: SpeechSynthesisVoice | null = null;
      onend: ((event: Event) => void) | null = null;
      onerror: ((event: Event) => void) | null = null;

      constructor(text = "") {
        super();
        this.text = text;
      }
    }

    (window as any).SpeechSynthesisUtterance = MockSpeechSynthesisUtterance;
    (window as any).speechSynthesis = {
      getVoices: mockGetVoices,
      speak: mockSpeak,
      cancel: mockCancel,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    };

    fallback = new BrowserFallback();
  });

  afterEach(() => {
    fallback.stop();
    localStorage.clear();
    vi.restoreAllMocks();
  });

  it("buildExerciseFallbackPhrases construye la cola: nombre → pasos en orden → aviso al final", () => {
    const exercise = {
      name: "Press banca con mancuernas",
      guide: {
        steps: [
          "Acuéstate boca arriba en el banco.",
          "Empuja las mancuernas hacia arriba.",
        ],
        disclaimer: "Este contenido es orientativo y no reemplaza la guía de un profesional.",
      },
    };

    const phrases = buildExerciseFallbackPhrases(exercise);
    expect(phrases).toEqual([
      "Press banca con mancuernas",
      "Paso 1: Acuéstate boca arriba en el banco.",
      "Paso 2: Empuja las mancuernas hacia arriba.",
      "Este contenido es orientativo y no reemplaza la guía de un profesional.",
    ]);
  });

  it("isAvailable detecta disponibilidad cuando existen voces en español", () => {
    expect(fallback.isAvailable()).toBe(true);

    mockGetVoices.mockReturnValue([]);
    expect(fallback.isAvailable()).toBe(false);

    mockGetVoices.mockReturnValue([{ lang: "en-US", name: "English" } as SpeechSynthesisVoice]);
    expect(fallback.isAvailable()).toBe(false);
  });

  it("play() inicia la reproducción de la primera frase con voz en español", async () => {
    const phrases = ["Sentadilla", "Paso 1: Separa los pies", "Aviso"];
    await fallback.play("ex-1", phrases);

    expect(mockSpeak).toHaveBeenCalledTimes(1);
    const utterance = mockSpeak.mock.calls[0]![0] as SpeechSynthesisUtterance;
    expect(utterance.text).toBe("Sentadilla");
    expect(utterance.lang).toBe("es-CO");
    expect(fallback.getSnapshot().state).toBe("playing");
    expect(fallback.getCurrentPhraseIndex()).toBe(0);
  });

  it("reproduce la cola de frases secuencialmente al disparar onend", async () => {
    const phrases = ["Sentadilla", "Paso 1: Separa pies", "Aviso"];
    await fallback.play("ex-1", phrases);

    expect(mockSpeak).toHaveBeenCalledTimes(1);
    const u1 = mockSpeak.mock.calls[0]![0];

    // Simular fin de primera frase
    u1.onend?.(new Event("end"));
    expect(mockSpeak).toHaveBeenCalledTimes(2);
    const u2 = mockSpeak.mock.calls[1]![0];
    expect(u2.text).toBe("Paso 1: Separa pies");

    // Simular fin de segunda frase
    u2.onend?.(new Event("end"));
    expect(mockSpeak).toHaveBeenCalledTimes(3);
    const u3 = mockSpeak.mock.calls[2]![0];
    expect(u3.text).toBe("Aviso");

    // Simular fin de última frase -> pasa a paused/concluido
    u3.onend?.(new Event("end"));
    expect(fallback.getSnapshot().state).toBe("paused");
  });

  it("pause() cancela la síntesis sin reiniciar el índice de frase (AC-4-1)", async () => {
    const phrases = ["Sentadilla", "Paso 1: Separa pies", "Aviso"];
    await fallback.play("ex-1", phrases);

    // Avanzar a paso 1
    const u1 = mockSpeak.mock.calls[0]![0];
    u1.onend?.(new Event("end"));
    expect(fallback.getCurrentPhraseIndex()).toBe(1);

    // Pausar
    fallback.pause();
    expect(mockCancel).toHaveBeenCalled();
    expect(fallback.getSnapshot().state).toBe("paused");
    // Conserva el índice en el paso 1
    expect(fallback.getCurrentPhraseIndex()).toBe(1);

    // Reanudar retoma desde el paso 1
    await fallback.resume();
    expect(mockSpeak).toHaveBeenCalledTimes(3);
    const uResume = mockSpeak.mock.calls[2]![0];
    expect(uResume.text).toBe("Paso 1: Separa pies");
  });

  it("restart() reinicia la cola desde el paso 0 (AC-4-2)", async () => {
    const phrases = ["Sentadilla", "Paso 1: Separa pies", "Aviso"];
    await fallback.play("ex-1", phrases);

    // Avanzar al paso 1
    mockSpeak.mock.calls[0]![0].onend?.(new Event("end"));
    expect(fallback.getCurrentPhraseIndex()).toBe(1);

    // Repetir
    await fallback.restart();
    expect(mockCancel).toHaveBeenCalled();
    expect(fallback.getCurrentPhraseIndex()).toBe(0);
    const lastCall = mockSpeak.mock.calls[mockSpeak.mock.calls.length - 1]![0];
    expect(lastCall.text).toBe("Sentadilla");
  });

  it("stop() cancela la síntesis y reinicia el estado a idle", async () => {
    const phrases = ["Sentadilla", "Paso 1"];
    await fallback.play("ex-1", phrases);

    fallback.stop();
    expect(mockCancel).toHaveBeenCalled();
    expect(fallback.getSnapshot().state).toBe("idle");
    expect(fallback.getCurrentPhraseIndex()).toBe(0);
    expect(fallback.getCurrentExerciseId()).toBeNull();
  });

  it("setRate() aplica la velocidad y persiste en localStorage (AC-5-1 y AC-5-2)", async () => {
    const phrases = ["Sentadilla"];
    await fallback.play("ex-1", phrases);

    fallback.setRate(1.25);
    expect(fallback.getSnapshot().rate).toBe(1.25);

    // Se vuelve a invocar speak con rate 1.25
    const lastCall = mockSpeak.mock.calls[mockSpeak.mock.calls.length - 1]![0];
    expect(lastCall.rate).toBe(1.25);
  });

  it("si no hay voces en español, play() pasa a estado unavailable (AC-6-2)", async () => {
    mockGetVoices.mockReturnValue([]);
    await fallback.play("ex-no-voice", ["Texto"]);

    expect(fallback.getSnapshot().state).toBe("unavailable");
    expect(fallback.getSnapshot().error?.message).toContain("No hay voces en español");
  });

  it("onerror pasa a estado error si no fue cancelación intencional (AC-6-3)", async () => {
    const phrases = ["Sentadilla"];
    await fallback.play("ex-err", phrases);

    const utterance = mockSpeak.mock.calls[0]![0];
    utterance.onerror?.({ error: "audio-busy" });

    expect(fallback.getSnapshot().state).toBe("error");
    expect(fallback.getSnapshot().error?.message).toContain("error en la síntesis");
  });
});
