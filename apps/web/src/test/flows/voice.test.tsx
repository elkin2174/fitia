import { act, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { globalAudioPlayer } from "../../features/voice/AudioPlayer";
import { globalBrowserFallback } from "../../features/voice/BrowserFallback";
import {
  PLAYBACK_RATE_STORAGE_KEY,
} from "../../features/voice/playbackRate";
import {
  EXERCISE_DISCLAIMER,
  ME,
  exerciseFixture,
  planDayDetailFixture,
  todayPlanFixture,
} from "../fixtures";
import { pathOf, renderRoute } from "../render";
import { API, apiError, http, HttpResponse, ok, sent, server } from "../server";

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

describe("HU 3, HU 4, HU 5 y HU 6 — Audio de ejercicios y respaldo con voz del navegador", () => {
  let mockPlay: ReturnType<typeof vi.fn>;
  let mockPause: ReturnType<typeof vi.fn>;
  let mockLoad: ReturnType<typeof vi.fn>;
  let mockCreateObjectURL: ReturnType<typeof vi.fn>;
  let mockRevokeObjectURL: ReturnType<typeof vi.fn>;
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

  const FAKE_WAV = new Uint8Array([82, 73, 70, 70, 36, 0, 0, 0, 87, 65, 86, 69]); // RIFF...WAVE

  beforeEach(() => {
    localStorage.clear();
    globalAudioPlayer.stop();
    globalAudioPlayer.clearCache();
    globalBrowserFallback.stop();

    mockPlay = vi.fn().mockImplementation(async function (this: HTMLAudioElement) {
      this.dispatchEvent(new Event("play"));
      return Promise.resolve();
    });
    mockPause = vi.fn().mockImplementation(function (this: HTMLAudioElement) {
      this.dispatchEvent(new Event("pause"));
    });
    mockLoad = vi.fn();
    mockCreateObjectURL = vi.fn(() => "blob:http://localhost/mock-audio-wav");
    mockRevokeObjectURL = vi.fn();

    window.HTMLMediaElement.prototype.play = mockPlay as unknown as () => Promise<void>;
    window.HTMLMediaElement.prototype.pause = mockPause as unknown as () => void;
    window.HTMLMediaElement.prototype.load = mockLoad as unknown as () => void;
    window.URL.createObjectURL = mockCreateObjectURL as unknown as (obj: Blob | MediaSource) => string;
    window.URL.revokeObjectURL = mockRevokeObjectURL as unknown as (url: string) => void;

    mockSpeak = vi.fn();
    mockCancel = vi.fn();
    mockGetVoices = vi.fn().mockReturnValue([SPANISH_VOICE]);

    (window as any).SpeechSynthesisUtterance = MockSpeechSynthesisUtterance;
    (window as any).speechSynthesis = {
      getVoices: mockGetVoices,
      speak: mockSpeak,
      cancel: mockCancel,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    };
  });

  afterEach(() => {
    globalAudioPlayer.stop();
    globalAudioPlayer.clearCache();
    globalBrowserFallback.stop();
    localStorage.clear();
    vi.restoreAllMocks();
  });

  function setupExercise(exerciseId = "e1111111-1111-1111-1111-111111111111") {
    const exercise = exerciseFixture({
      id: exerciseId,
      name: "Sentadilla con peso corporal",
      guide: {
        steps: [
          "Separa los pies al ancho de los hombros.",
          "Baja la cadera como si fueras a sentarte en una silla.",
        ],
        disclaimer: EXERCISE_DISCLAIMER,
      },
    });

    const todayData = todayPlanFixture({
      day: planDayDetailFixture({ exercises: [exercise] }),
    });

    server.use(
      http.get(`${API}/plan/today`, () => ok(todayData)),
      http.get(`${API}/plan/exercises/${exerciseId}/audio`, () => {
        return new HttpResponse(FAKE_WAV, {
          headers: { "Content-Type": "audio/wav" },
        });
      }),
    );

    return { exercise, todayData };
  }

  it("AC-3-1: al pulsar «Escuchar» se pide el audio con IA y NO se usa la voz del navegador si funciona", async () => {
    const { exercise } = setupExercise();
    const { user } = renderRoute(`/hoy?ejercicio=${exercise.id}`, { me: ME });

    expect(await screen.findByRole("dialog")).toBeInTheDocument();

    const listenBtn = screen.getByRole("button", { name: "Escuchar" });
    expect(listenBtn).toBeInTheDocument();

    await user.click(listenBtn);

    expect(sent("GET", `/plan/exercises/${exercise.id}/audio`)).toHaveLength(1);
    expect(mockPlay).toHaveBeenCalledTimes(1);
    // Como la IA funcionó correctamente, no se usó el respaldo del navegador
    expect(mockSpeak).not.toHaveBeenCalled();
    expect(screen.queryByText("Voz del dispositivo")).not.toBeInTheDocument();
  });

  it("AC-3-2: durante la carga aparece «Preparando audio…» y clics repetidos no duplican peticiones", async () => {
    const exercise = exerciseFixture({ id: "e-loading-test" });
    let resolveResponse!: (res: Response) => void;
    const pendingPromise = new Promise<Response>((resolve) => {
      resolveResponse = resolve;
    });

    server.use(
      http.get(
        `${API}/plan/today`,
        () => ok(todayPlanFixture({ day: planDayDetailFixture({ exercises: [exercise] }) })),
      ),
      http.get(`${API}/plan/exercises/${exercise.id}/audio`, () => pendingPromise),
    );

    const { user } = renderRoute(`/hoy?ejercicio=${exercise.id}`, { me: ME });
    expect(await screen.findByRole("dialog")).toBeInTheDocument();

    const listenBtn = screen.getByRole("button", { name: "Escuchar" });

    // Primer clic inicia carga
    await user.click(listenBtn);

    // Debe mostrar «Preparando audio…» y estar deshabilitado
    const busyBtn = screen.getByRole("button", { name: "Preparando audio…" });
    expect(busyBtn).toBeDisabled();

    // Intentar segundo clic
    await user.click(busyBtn);

    // Solo se debe haber emitido una única petición a la red
    expect(sent("GET", `/plan/exercises/${exercise.id}/audio`)).toHaveLength(1);

    // Resolver la respuesta
    resolveResponse(new HttpResponse(FAKE_WAV, { headers: { "Content-Type": "audio/wav" } }));
  });

  it("AC-3-3: la segunda reproducción del mismo ejercicio no vuelve a pedir el audio (caché en memoria)", async () => {
    const { exercise } = setupExercise();
    const { user } = renderRoute(`/hoy?ejercicio=${exercise.id}`, { me: ME });

    expect(await screen.findByRole("dialog")).toBeInTheDocument();

    const listenBtn = screen.getByRole("button", { name: "Escuchar" });
    await user.click(listenBtn);

    expect(sent("GET", `/plan/exercises/${exercise.id}/audio`)).toHaveLength(1);

    // Pausar
    const pauseBtn = await screen.findByRole("button", { name: "Pausar" });
    await user.click(pauseBtn);

    // Reanudar
    const resumeBtn = screen.getByRole("button", { name: "Reanudar" });
    await user.click(resumeBtn);

    // Sigue siendo 1 sola llamada a la red (el audio vino de la caché)
    expect(sent("GET", `/plan/exercises/${exercise.id}/audio`)).toHaveLength(1);
  });

  it("AC-3-4: cerrar la explicación detiene el audio", async () => {
    const { exercise } = setupExercise();
    const { user, router } = renderRoute(`/hoy?ejercicio=${exercise.id}`, { me: ME });

    expect(await screen.findByRole("dialog")).toBeInTheDocument();

    const listenBtn = screen.getByRole("button", { name: "Escuchar" });
    await user.click(listenBtn);

    // Cerrar con el botón cerrar
    const closeBtn = screen.getByRole("button", { name: "Cerrar explicación" });
    await user.click(closeBtn);

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(pathOf(router)).toBe("/hoy");
    expect(mockPause).toHaveBeenCalled();
  });

  it("AC-3-5: nunca suenan dos audios a la vez; iniciar otro detiene el anterior", async () => {
    const ex1 = exerciseFixture({ id: "e1", name: "Ejercicio 1" });
    const ex2 = exerciseFixture({ id: "e2", name: "Ejercicio 2" });

    server.use(
      http.get(
        `${API}/plan/today`,
        () => ok(todayPlanFixture({ day: planDayDetailFixture({ exercises: [ex1, ex2] }) })),
      ),
      http.get(`${API}/plan/exercises/e1/audio`, () => new HttpResponse(FAKE_WAV, { headers: { "Content-Type": "audio/wav" } })),
      http.get(`${API}/plan/exercises/e2/audio`, () => new HttpResponse(FAKE_WAV, { headers: { "Content-Type": "audio/wav" } })),
    );

    const { user, router } = renderRoute(`/hoy?ejercicio=e1`, { me: ME });
    expect(await screen.findByRole("dialog")).toBeInTheDocument();

    // Reproducir ejercicio 1
    await user.click(screen.getByRole("button", { name: "Escuchar" }));
    expect(sent("GET", "/plan/exercises/e1/audio")).toHaveLength(1);

    // Cambiar al ejercicio 2 en la URL
    router.navigate("/hoy?ejercicio=e2");
    expect(await screen.findByRole("heading", { name: "Ejercicio 2" })).toBeInTheDocument();

    // Reproducir ejercicio 2
    await user.click(screen.getByRole("button", { name: "Escuchar" }));

    // El anterior se pausó y se ejecutó la reproducción del segundo
    expect(mockPause).toHaveBeenCalled();
    expect(sent("GET", "/plan/exercises/e2/audio")).toHaveLength(1);
    expect(globalAudioPlayer.getCurrentExerciseId()).toBe("e2");
  });

  it("AC-3-6: los botones y mensajes están en español y tienen nombre accesible", async () => {
    const { exercise } = setupExercise();
    renderRoute(`/hoy?ejercicio=${exercise.id}`, { me: ME });

    expect(await screen.findByRole("dialog")).toBeInTheDocument();

    expect(screen.getByRole("button", { name: "Escuchar" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Reanudar" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Repetir" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Velocidad 0,75×" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Velocidad 1×" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Velocidad 1,25×" })).toBeInTheDocument();
  });

  it("AC-4-1 a AC-4-3: pausa, reanudar, repetir y estado deshabilitado sin audio", async () => {
    const { exercise } = setupExercise();
    const { user } = renderRoute(`/hoy?ejercicio=${exercise.id}`, { me: ME });

    expect(await screen.findByRole("dialog")).toBeInTheDocument();

    // Sin audio iniciado: pausar/reanudar y repetir están deshabilitados (AC-4-3)
    const toggleBtn = screen.getByRole("button", { name: "Reanudar" });
    const repeatBtn = screen.getByRole("button", { name: "Repetir" });
    expect(toggleBtn).toBeDisabled();
    expect(repeatBtn).toBeDisabled();

    // Iniciar audio
    await user.click(screen.getByRole("button", { name: "Escuchar" }));

    // Ahora el botón pasa a ser «Pausar» y está habilitado
    const pauseBtn = await screen.findByRole("button", { name: "Pausar" });
    expect(pauseBtn).not.toBeDisabled();
    expect(repeatBtn).not.toBeDisabled();

    // Pausar (AC-4-1)
    await user.click(pauseBtn);
    expect(mockPause).toHaveBeenCalled();

    // Ahora es «Reanudar»
    const resumeBtn = screen.getByRole("button", { name: "Reanudar" });
    expect(resumeBtn).not.toBeDisabled();

    // Reanudar (AC-4-1)
    await user.click(resumeBtn);
    expect(mockPlay).toHaveBeenCalled();

    // Repetir (AC-4-2)
    await user.click(repeatBtn);
    const audio = globalAudioPlayer.getAudio();
    expect(audio.currentTime).toBe(0);
    expect(mockPlay).toHaveBeenCalled();
  });

  it("AC-4-4: los controles se operan con teclado", async () => {
    const { exercise } = setupExercise();
    const { user } = renderRoute(`/hoy?ejercicio=${exercise.id}`, { me: ME });

    expect(await screen.findByRole("dialog")).toBeInTheDocument();

    const listenBtn = screen.getByRole("button", { name: "Escuchar" });
    listenBtn.focus();
    expect(listenBtn).toHaveFocus();

    // Activar con tecla Enter
    await user.keyboard("{Enter}");
    expect(mockPlay).toHaveBeenCalledTimes(1);

    const pauseBtn = await screen.findByRole("button", { name: "Pausar" });
    pauseBtn.focus();
    await user.keyboard(" "); // Espacio para pausar
    expect(mockPause).toHaveBeenCalledTimes(1);
  });

  it("AC-5-1 a AC-5-3: velocidad 0,75×, 1×, 1,25×, persistencia y resiliencia en localStorage", async () => {
    const { exercise } = setupExercise();
    const { user } = renderRoute(`/hoy?ejercicio=${exercise.id}`, { me: ME });

    expect(await screen.findByRole("dialog")).toBeInTheDocument();

    // Iniciar audio
    await user.click(screen.getByRole("button", { name: "Escuchar" }));
    const audio = globalAudioPlayer.getAudio();
    audio.currentTime = 3.5;

    // Cambiar a 1,25× (AC-5-1)
    const btn125 = screen.getByRole("button", { name: "Velocidad 1,25×" });
    await user.click(btn125);

    expect(audio.playbackRate).toBe(1.25);
    expect(audio.preservesPitch).toBe(true);
    expect(audio.currentTime).toBe(3.5); // No reinició la posición (AC-5-1)

    // Persistencia en localStorage (AC-5-2)
    expect(localStorage.getItem(PLAYBACK_RATE_STORAGE_KEY)).toBe("1.25");

    // Cambiar a 0,75×
    const btn075 = screen.getByRole("button", { name: "Velocidad 0,75×" });
    await user.click(btn075);
    expect(audio.playbackRate).toBe(0.75);
    expect(localStorage.getItem(PLAYBACK_RATE_STORAGE_KEY)).toBe("0.75");
  });

  it("AC-6-1: si el endpoint responde 503 AI_UNAVAILABLE, conmuta automáticamente a voz del navegador en español en orden", async () => {
    const exercise = exerciseFixture({
      id: "e-fail-503",
      name: "Flexión de pecho",
      guide: {
        steps: ["Coloca las manos en el piso.", "Baja el pecho controlando."],
        disclaimer: "Aviso orientativo.",
      },
    });

    server.use(
      http.get(
        `${API}/plan/today`,
        () => ok(todayPlanFixture({ day: planDayDetailFixture({ exercises: [exercise] }) })),
      ),
      http.get(`${API}/plan/exercises/${exercise.id}/audio`, () => {
        return apiError(503, "AI_UNAVAILABLE", "Servicio no disponible.");
      }),
    );

    const { user } = renderRoute(`/hoy?ejercicio=${exercise.id}`, { me: ME });
    expect(await screen.findByRole("dialog")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Escuchar" }));

    // No se pudo reproducir WAV con IA
    expect(mockPlay).not.toHaveBeenCalled();

    // Conmutó automáticamente a la voz del navegador
    expect(mockSpeak).toHaveBeenCalled();
    const firstUtterance = mockSpeak.mock.calls[0]![0];
    expect(firstUtterance.text).toBe("Flexión de pecho");

    // Indicador discreto «Voz del dispositivo»
    expect(await screen.findByText("Voz del dispositivo")).toBeInTheDocument();

    // Simular lectura de pasos sucesivos
    firstUtterance.onend?.(new Event("end"));
    const secondUtterance = mockSpeak.mock.calls[1]![0];
    expect(secondUtterance.text).toBe("Paso 1: Coloca las manos en el piso.");

    secondUtterance.onend?.(new Event("end"));
    const thirdUtterance = mockSpeak.mock.calls[2]![0];
    expect(thirdUtterance.text).toBe("Paso 2: Baja el pecho controlando.");

    thirdUtterance.onend?.(new Event("end"));
    const fourthUtterance = mockSpeak.mock.calls[3]![0];
    expect(fourthUtterance.text).toBe("Aviso orientativo.");
  });

  it("AC-6-1: si el endpoint tarda más de 15 s, se aborta y se conmuta a la voz del navegador", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });

    const exercise = exerciseFixture({ id: "e-slow-timeout" });
    const pendingPromise = new Promise<Response>(() => {}); // Nunca resuelve

    server.use(
      http.get(
        `${API}/plan/today`,
        () => ok(todayPlanFixture({ day: planDayDetailFixture({ exercises: [exercise] }) })),
      ),
      http.get(`${API}/plan/exercises/${exercise.id}/audio`, () => pendingPromise),
    );

    const { user } = renderRoute(`/hoy?ejercicio=${exercise.id}`, {
      me: ME,
      advanceTimers: (ms) => vi.advanceTimersByTime(ms),
    });
    expect(await screen.findByRole("dialog")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Escuchar" }));

    // Inicialmente cargando IA
    expect(mockSpeak).not.toHaveBeenCalled();

    // Avanzar 15 segundos con temporizadores falsos
    await act(async () => {
      vi.advanceTimersByTime(15000);
    });

    // Debe haberse activado el fallback a voz del navegador
    expect(mockSpeak).toHaveBeenCalled();
    expect(await screen.findByText("Voz del dispositivo")).toBeInTheDocument();

    vi.useRealTimers();
  });

  it("AC-6-2: sin soporte de voz en el navegador ni voces en español, botón queda deshabilitado con aviso", async () => {
    mockGetVoices.mockReturnValue([]); // Cero voces en español

    const exercise = exerciseFixture({
      id: "e-no-voices",
      guide: {
        steps: ["Separa los pies al ancho de los hombros."],
        disclaimer: EXERCISE_DISCLAIMER,
      },
    });
    server.use(
      http.get(
        `${API}/plan/today`,
        () => ok(todayPlanFixture({ day: planDayDetailFixture({ exercises: [exercise] }) })),
      ),
      http.get(`${API}/plan/exercises/${exercise.id}/audio`, () => {
        return apiError(503, "AI_UNAVAILABLE");
      }),
    );

    const { user } = renderRoute(`/hoy?ejercicio=${exercise.id}`, { me: ME });
    expect(await screen.findByRole("dialog")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Escuchar" }));

    // Botón queda deshabilitado y se muestra aviso en español (AC-6-2)
    const btn = screen.getByRole("button", { name: "Escuchar" });
    expect(btn).toBeDisabled();
    expect(
      await screen.findByText(
        "Tu dispositivo no tiene voz en español disponible. Puedes leer la explicación en pantalla.",
      ),
    ).toBeInTheDocument();

    // Los pasos en texto siguen intactos y visibles
    expect(screen.getByText("Separa los pies al ancho de los hombros.")).toBeInTheDocument();
  });

  it("AC-6-3: error a mitad de lectura detiene el audio y el sheet permanece usable", async () => {
    const exercise = exerciseFixture({ id: "e-mid-error" });
    server.use(
      http.get(
        `${API}/plan/today`,
        () => ok(todayPlanFixture({ day: planDayDetailFixture({ exercises: [exercise] }) })),
      ),
      http.get(`${API}/plan/exercises/${exercise.id}/audio`, () => {
        return apiError(503, "AI_UNAVAILABLE");
      }),
    );

    const { user } = renderRoute(`/hoy?ejercicio=${exercise.id}`, { me: ME });
    expect(await screen.findByRole("dialog")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Escuchar" }));
    expect(mockSpeak).toHaveBeenCalled();

    // Simular error a mitad de la frase
    const utterance = mockSpeak.mock.calls[0]![0];
    act(() => {
      utterance.onerror?.({ error: "audio-busy" });
    });

    // Muestra el banner de error sin bloquear la interfaz
    expect(await screen.findByText("No pudimos generar el audio")).toBeInTheDocument();
    expect(screen.getByText("Ocurrió un error en la síntesis de voz del dispositivo.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Reintentar" })).toBeInTheDocument();

    // La hoja sigue operativa y el botón de cerrar funciona
    const closeBtn = screen.getByRole("button", { name: "Cerrar explicación" });
    await user.click(closeBtn);
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("pausa, repetir y velocidad funcionan con el motor de respaldo del navegador", async () => {
    const exercise = exerciseFixture({ id: "e-fallback-controls" });
    server.use(
      http.get(
        `${API}/plan/today`,
        () => ok(todayPlanFixture({ day: planDayDetailFixture({ exercises: [exercise] }) })),
      ),
      http.get(`${API}/plan/exercises/${exercise.id}/audio`, () => {
        return apiError(503, "AI_UNAVAILABLE");
      }),
    );

    const { user } = renderRoute(`/hoy?ejercicio=${exercise.id}`, { me: ME });
    expect(await screen.findByRole("dialog")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Escuchar" }));
    expect(mockSpeak).toHaveBeenCalled();

    // Pausar con motor de respaldo
    const pauseBtn = await screen.findByRole("button", { name: "Pausar" });
    await user.click(pauseBtn);
    expect(mockCancel).toHaveBeenCalled();

    // Reanudar
    const resumeBtn = screen.getByRole("button", { name: "Reanudar" });
    await user.click(resumeBtn);
    expect(mockSpeak).toHaveBeenCalledTimes(2);

    // Repetir
    const repeatBtn = screen.getByRole("button", { name: "Repetir" });
    await user.click(repeatBtn);
    expect(mockCancel).toHaveBeenCalled();
    const lastCall = mockSpeak.mock.calls[mockSpeak.mock.calls.length - 1]![0];
    expect(lastCall.text).toBe(exercise.name);

    // Cambiar velocidad
    const btn125 = screen.getByRole("button", { name: "Velocidad 1,25×" });
    await user.click(btn125);
    expect(localStorage.getItem(PLAYBACK_RATE_STORAGE_KEY)).toBe("1.25");
  });
});
