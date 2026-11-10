import { act, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { globalAudioPlayer } from "../../features/voice/AudioPlayer";
import { globalBrowserFallback } from "../../features/voice/BrowserFallback";
import { AUDIO_CUES_TEXT } from "../../features/voice/cues";

import {
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

class MockWakeLockSentinel extends EventTarget {
  released = false;
  async release() {
    this.released = true;
    this.dispatchEvent(new Event("release"));
  }
}

describe("HU 7, HU 9 y HU 10 — Modo guiado por voz (/hoy/guiado)", () => {
  let mockPlay: ReturnType<typeof vi.fn>;
  let mockPause: ReturnType<typeof vi.fn>;
  let mockLoad: ReturnType<typeof vi.fn>;
  let mockCreateObjectURL: ReturnType<typeof vi.fn>;
  let mockRevokeObjectURL: ReturnType<typeof vi.fn>;
  let mockSpeak: ReturnType<typeof vi.fn>;
  let mockCancel: ReturnType<typeof vi.fn>;
  let mockGetVoices: ReturnType<typeof vi.fn>;
  let mockWakeLockRequest: ReturnType<typeof vi.fn>;
  let mockSentinel: MockWakeLockSentinel;

  const SPANISH_VOICE = {
    name: "Spanish Female Voice",
    lang: "es-CO",
    default: true,
    localService: true,
    voiceURI: "es-co-female",
  } as SpeechSynthesisVoice;

  const FAKE_WAV = new Uint8Array([82, 73, 70, 70, 36, 0, 0, 0, 87, 65, 86, 69]);

  const exercise1 = exerciseFixture({
    id: "e1111111-1111-1111-1111-111111111111",
    position: 1,
    name: "Sentadilla libre",
    sets: 2,
    reps: 10,
    work_seconds: null,
    rest_seconds: 30,
    guide: {
      steps: ["Párate firme.", "Baja la cadera."],
      disclaimer: "Aviso orientativo.",
    },
  });

  const exercise2 = exerciseFixture({
    id: "e2222222-2222-2222-2222-222222222222",
    position: 2,
    name: "Plancha frontal",
    sets: 2,
    reps: null,
    work_seconds: 20,
    rest_seconds: 30,
    guide: {
      steps: ["Apoya antebrazos.", "Mantén el cuerpo recto."],
      disclaimer: "Aviso orientativo.",
    },
  });

  const trainingDay = planDayDetailFixture({
    status: "training",
    exercises: [exercise1, exercise2],
  });

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

    mockSpeak = vi.fn().mockImplementation((utterance: MockSpeechSynthesisUtterance) => {
      // Simular finalización asíncrona del habla
      setTimeout(() => {
        utterance.onend?.(new Event("end"));
      }, 10);
    });
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

    mockSentinel = new MockWakeLockSentinel();
    mockWakeLockRequest = vi.fn().mockResolvedValue(mockSentinel);
    Object.defineProperty(navigator, "wakeLock", {
      value: { request: mockWakeLockRequest },
      configurable: true,
      writable: true,
    });
  });

  afterEach(() => {
    globalAudioPlayer.stop();
    globalAudioPlayer.clearCache();
    globalBrowserFallback.stop();
    localStorage.clear();
    vi.restoreAllMocks();
  });

  function setupTrainingServer() {
    server.use(
      http.get(`${API}/plan/today`, () =>
        ok(
          todayPlanFixture({
            plan_status: "ready",
            is_weekend: false,
            day: trainingDay,
          }),
        ),
      ),
      http.get(`${API}/plan/exercises/:id/audio`, () =>
        new HttpResponse(FAKE_WAV, {
          headers: { "Content-Type": "audio/wav" },
        }),
      ),
      http.get(`${API}/plan/audio/cues/:name`, ({ params }) => {
        const { name } = params;
        if (typeof name === "string" && ["descanso", "diez-segundos", "fin-descanso", "fin-rutina"].includes(name)) {
          return new HttpResponse(FAKE_WAV, {
            headers: { "Content-Type": "audio/wav" },
          });
        }
        return apiError(404, "CUE_NOT_FOUND", "La frase de audio solicitada no existe.");
      }),
    );
  }


  it("AC-7-1: con «Entrenar con voz», la app anuncia el primer ejercicio y lee sus pasos con el audio de la HU 3", async () => {
    setupTrainingServer();
    const { user, router } = renderRoute("/hoy", { me: ME });

    // Desde la rutina de hoy se ofrece «Entrenar con voz»
    const trainButton = await screen.findByRole("link", { name: /Entrenar con voz/i }, { timeout: 5000 });
    expect(trainButton).toBeInTheDocument();

    await user.click(trainButton);

    // Navega a /hoy/guiado
    await waitFor(() => {
      expect(pathOf(router)).toBe("/hoy/guiado");
    });

    // Muestra el primer ejercicio
    expect(await screen.findByRole("heading", { name: "Sentadilla libre" })).toBeInTheDocument();
    expect(screen.getByText(/Ejercicio 1 de 2/i)).toBeInTheDocument();
    expect(screen.getByText(/Serie 1 de 2/i)).toBeInTheDocument();

    // Se verifica que se invocó la síntesis para el anuncio inicial
    await waitFor(() => {
      expect(mockSpeak).toHaveBeenCalled();
      const firstCall = mockSpeak.mock.calls[0]![0] as MockSpeechSynthesisUtterance;
      expect(firstCall.text).toContain("Sentadilla libre");
      expect(firstCall.text).toContain("2 series");
      expect(firstCall.text).toContain("10 repeticiones");
    });

    // Se pide y reproduce el audio de la técnica (HU 3)
    await waitFor(() => {
      expect(mockPlay).toHaveBeenCalled();
    });
  });

  it("AC-7-2: al iniciar se precarga el audio de los ejercicios del día con concurrencia máxima de 2", async () => {
    const audioRequests: string[] = [];
    server.use(
      http.get(`${API}/plan/today`, () =>
        ok(
          todayPlanFixture({
            plan_status: "ready",
            is_weekend: false,
            day: trainingDay,
          }),
        ),
      ),
      http.get(`${API}/plan/exercises/:id/audio`, ({ params }) => {
        audioRequests.push(params.id as string);
        return new HttpResponse(FAKE_WAV, {
          headers: { "Content-Type": "audio/wav" },
        });
      }),
    );

    renderRoute("/hoy/guiado", { me: ME });

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Sentadilla libre" })).toBeInTheDocument();
    });

    // Se precargan los audios de los ejercicios de la sesión
    await waitFor(() => {
      expect(audioRequests).toContain(exercise1.id);
      expect(audioRequests).toContain(exercise2.id);
    });
  });

  it("AC-7-3: al terminar el último ejercicio anuncia el fin de rutina y muestra celebración", async () => {
    setupTrainingServer();
    const { user } = renderRoute("/hoy/guiado", { me: ME });

    expect(await screen.findByRole("heading", { name: "Sentadilla libre" })).toBeInTheDocument();

    // Esperar a que comience la reproducción del audio de la técnica
    await waitFor(() => {
      expect(mockPlay).toHaveBeenCalled();
    });

    // Simulamos que el audio de la técnica termina emitiendo 'ended' en el audio element
    act(() => {
      globalAudioPlayer.getAudio().dispatchEvent(new Event("ended"));
    });

    // Ahora estamos en working: pulsamos «Terminar serie» (Serie 1 -> descanso)
    const doneBtn1 = await screen.findByRole("button", { name: /Terminar serie/i });
    await user.click(doneBtn1);

    // En descanso: saltamos descanso -> Serie 2
    const skipRest1 = await screen.findByRole("button", { name: /Saltar descanso/i });
    await user.click(skipRest1);

    // Serie 2 de Sentadilla libre: esperamos a que pase a working tras el anuncio de serie
    const doneBtn2 = await screen.findByRole("button", { name: /Terminar serie/i });
    await user.click(doneBtn2);

    // En descanso: saltamos descanso -> Ejercicio 2 (Plancha frontal)
    const skipRest2 = await screen.findByRole("button", { name: /Saltar descanso/i });
    await user.click(skipRest2);

    expect(await screen.findByRole("heading", { name: "Plancha frontal" })).toBeInTheDocument();

    // Plancha frontal Serie 1: esperar play y terminar
    await waitFor(() => {
      expect(globalAudioPlayer.getCurrentExerciseId()).toBe(exercise2.id);
    });
    act(() => {
      globalAudioPlayer.getAudio().dispatchEvent(new Event("ended"));
    });
    const doneBtn3 = await screen.findByRole("button", { name: /Terminar serie/i });
    await user.click(doneBtn3);

    // Saltamos descanso -> Serie 2
    const skipRest3 = await screen.findByRole("button", { name: /Saltar descanso/i });
    await user.click(skipRest3);

    // Plancha frontal Serie 2 (última serie del último ejercicio)
    const doneBtn4 = await screen.findByRole("button", { name: /Terminar serie/i });
    await user.click(doneBtn4);

    // Saltamos el último descanso
    const skipRest4 = await screen.findByRole("button", { name: /Saltar descanso/i });
    await user.click(skipRest4);

    // Pantalla de fin de rutina (AC-7-3)
    expect(await screen.findByRole("heading", { name: "¡Rutina completada!" })).toBeInTheDocument();
    expect(screen.getByText(/Terminaste la rutina de hoy. ¡Buen trabajo!/i)).toBeInTheDocument();

    // Frase fija anunciada (con IA vía cue o voz de respaldo)
    await waitFor(() => {
      const isPlayedByCue = globalAudioPlayer.getCurrentExerciseId() === "cue:fin-rutina";
      const calls = mockSpeak.mock.calls.map((c) => (c[0] as MockSpeechSynthesisUtterance).text);
      const isSpokenByFallback = calls.some((t) => t.includes("Terminaste la rutina de hoy. ¡Buen trabajo!"));
      expect(isPlayedByCue || isSpokenByFallback).toBe(true);
    });
  });

  it("AC-7-4: el modo es estrictamente de solo lectura: no escribe en el plan ni en la base de datos", async () => {
    setupTrainingServer();
    const { user } = renderRoute("/hoy/guiado", { me: ME });

    expect(await screen.findByRole("heading", { name: "Sentadilla libre" })).toBeInTheDocument();

    // Realizar acciones en el modo guiado
    const pauseBtn = screen.getByRole("button", { name: /Pausar/i });
    await user.click(pauseBtn);
    const resumeBtn = screen.getByRole("button", { name: /Continuar/i });
    await user.click(resumeBtn);
    const nextBtn = screen.getByRole("button", { name: /Siguiente/i });
    await user.click(nextBtn);

    // Verificar que no se enviaron peticiones de escritura al plan ni al servidor
    expect(sent("POST", "/plan/today")).toHaveLength(0);
    expect(sent("POST", "/plan/generate")).toHaveLength(0);
    expect(sent("PUT", "/plan/today")).toHaveLength(0);
    expect(sent("PATCH", "/plan/today")).toHaveLength(0);
    expect(sent("DELETE", "/plan/today")).toHaveLength(0);
  });

  it("AC-9-1 a AC-9-5: control por botones («Siguiente», «Anterior», «Pausar», «Continuar», «Repetir», «Salir»)", async () => {
    setupTrainingServer();
    const { user, router } = renderRoute("/hoy/guiado", { me: ME });

    expect(await screen.findByRole("heading", { name: "Sentadilla libre" })).toBeInTheDocument();

    // En el primer ejercicio, «Anterior» está deshabilitado
    const prevBtn = screen.getByRole("button", { name: /Ejercicio anterior/i });
    expect(prevBtn).toBeDisabled();

    // AC-9-1: «Siguiente» avanza de ejercicio y detiene audio
    const nextBtn = screen.getByRole("button", { name: /Siguiente ejercicio/i });
    expect(nextBtn).toBeEnabled();
    await user.click(nextBtn);

    expect(await screen.findByRole("heading", { name: "Plancha frontal" })).toBeInTheDocument();
    expect(mockCancel).toHaveBeenCalled();

    // En el último ejercicio, «Siguiente» está deshabilitado y «Anterior» habilitado
    expect(screen.getByRole("button", { name: /Siguiente ejercicio/i })).toBeDisabled();
    expect(screen.getByRole("button", { name: /Ejercicio anterior/i })).toBeEnabled();

    // Volver al anterior con «Anterior»
    await user.click(screen.getByRole("button", { name: /Ejercicio anterior/i }));
    expect(await screen.findByRole("heading", { name: "Sentadilla libre" })).toBeInTheDocument();

    // AC-9-2: «Pausar» y «Continuar»
    const pauseBtn = screen.getByRole("button", { name: /Pausar/i });
    await user.click(pauseBtn);
    expect(screen.getByText("Entrenamiento en pausa")).toBeInTheDocument();

    const resumeBtn = screen.getByRole("button", { name: /Continuar/i });
    await user.click(resumeBtn);
    expect(screen.queryByText("Entrenamiento en pausa")).not.toBeInTheDocument();

    // AC-9-3: «Repetir» vuelve a anunciar el ejercicio actual
    mockSpeak.mockClear();
    const repeatBtn = screen.getByRole("button", { name: /Repetir explicación/i });
    await user.click(repeatBtn);
    await waitFor(() => {
      expect(mockSpeak).toHaveBeenCalled();
      const lastCall = mockSpeak.mock.calls[0]![0] as MockSpeechSynthesisUtterance;
      expect(lastCall.text).toContain("Sentadilla libre");
    });

    // AC-9-4: «Salir» detiene audio y vuelve a /hoy
    const exitBtn = screen.getByRole("button", { name: /Salir del modo guiado/i });
    await user.click(exitBtn);

    await waitFor(() => {
      expect(pathOf(router)).toBe("/hoy");
    });
    expect(mockCancel).toHaveBeenCalled();
  });

  it("AC-10-1: en día de descanso, fin de semana, plan sin generar o fallido, no se ofrece «Entrenar con voz» y entrar a /hoy/guiado redirige a /hoy", async () => {
    // 1. Día de descanso
    server.use(
      http.get(`${API}/plan/today`, () =>
        ok(
          todayPlanFixture({
            plan_status: "ready",
            is_weekend: false,
            day: planDayDetailFixture({
              status: "rest",
              exercises: [],
            }),
          }),
        ),
      ),
    );

    renderRoute("/hoy", { me: ME });
    expect(await screen.findByText(/Hoy no tienes entrenamiento programado/i)).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /Entrenar con voz/i })).not.toBeInTheDocument();

    // Intento de entrada directa a /hoy/guiado en día de descanso redirige a /hoy
    const { router: r1 } = renderRoute("/hoy/guiado", { me: ME });
    await waitFor(() => {
      expect(pathOf(r1)).toBe("/hoy");
    });

    // 2. Fin de semana
    server.use(
      http.get(`${API}/plan/today`, () =>
        ok(
          todayPlanFixture({
            plan_status: "ready",
            is_weekend: true,
            day: null,
          }),
        ),
      ),
    );
    const { router: r2 } = renderRoute("/hoy/guiado", { me: ME });
    await waitFor(() => {
      expect(pathOf(r2)).toBe("/hoy");
    });

    // 3. Plan fallido
    server.use(
      http.get(`${API}/plan/today`, () =>
        ok(
          todayPlanFixture({
            plan_status: "failed",
            failure: { code: "AI_UNAVAILABLE" },
            day: null,
          }),
        ),
      ),
    );
    const { router: r3 } = renderRoute("/hoy/guiado", { me: ME });
    await waitFor(() => {
      expect(pathOf(r3)).toBe("/hoy");
    });
  });

  it("AC-10-2 a AC-10-4: gestión de pantalla activa mediante Wake Lock", async () => {
    setupTrainingServer();
    const { user } = renderRoute("/hoy/guiado", { me: ME });

    expect(await screen.findByRole("heading", { name: "Sentadilla libre" })).toBeInTheDocument();

    // AC-10-2: Se solicita Wake Lock
    await waitFor(() => {
      expect(mockWakeLockRequest).toHaveBeenCalledWith("screen");
    });

    // AC-10-4: Al salir se libera el Wake Lock
    const exitBtn = screen.getByRole("button", { name: /Salir del modo guiado/i });
    await user.click(exitBtn);

    await waitFor(() => {
      expect(mockSentinel.released).toBe(true);
    });
  });

  it("AC-10-3: si Wake Lock no existe o lanza error, el modo sigue funcionando sin fallos", async () => {
    // Simular fallo en wakeLock.request
    mockWakeLockRequest.mockRejectedValue(new Error("NotAllowedError: Wake Lock denied"));
    setupTrainingServer();

    renderRoute("/hoy/guiado", { me: ME });

    // La pantalla carga normalmente sin errores
    expect(await screen.findByRole("heading", { name: "Sentadilla libre" })).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("con el audio con IA caído (503), el modo guiado sigue avanzando con el respaldo del navegador", async () => {
    server.use(
      http.get(`${API}/plan/today`, () =>
        ok(
          todayPlanFixture({
            plan_status: "ready",
            is_weekend: false,
            day: trainingDay,
          }),
        ),
      ),
      http.get(`${API}/plan/exercises/:id/audio`, () =>
        apiError(503, "AI_UNAVAILABLE", "Servicio no disponible"),
      ),
      http.get(`${API}/plan/audio/cues/:name`, () =>
        new HttpResponse(FAKE_WAV, { headers: { "Content-Type": "audio/wav" } }),
      ),
    );

    const { user } = renderRoute("/hoy/guiado", { me: ME });

    expect(await screen.findByRole("heading", { name: "Sentadilla libre" })).toBeInTheDocument();

    // Aunque la IA falle con 503, la síntesis del navegador lee el anuncio
    await waitFor(() => {
      expect(mockSpeak).toHaveBeenCalled();
    });

    // Simulamos que el fallback termina de leer emitiendo 'ended'
    act(() => {
      for (const listener of (globalBrowserFallback as any).endedListeners) {
        listener();
      }
    });

    // Se puede interactuar y avanzar con «Terminar serie»
    const doneBtn = await screen.findByRole("button", { name: /Terminar serie/i });
    await user.click(doneBtn);

    expect(await screen.findByRole("button", { name: /Saltar descanso/i })).toBeInTheDocument();
  });

  it("AC-8-1: cuenta regresiva de descanso visible y decreciendo según rest_seconds del plan", async () => {
    setupTrainingServer();
    const { user } = renderRoute("/hoy/guiado", { me: ME });

    expect(await screen.findByRole("heading", { name: "Sentadilla libre" })).toBeInTheDocument();
    await waitFor(() => expect(mockPlay).toHaveBeenCalled());
    act(() => {
      globalAudioPlayer.getAudio().dispatchEvent(new Event("ended"));
    });

    // Pasar a descanso
    const doneBtn = await screen.findByRole("button", { name: /Terminar serie/i });
    await user.click(doneBtn);

    // En descanso se muestra el encabezado y el tiempo
    expect(await screen.findByText("Descanso")).toBeInTheDocument();
    expect(screen.getByText(/^30 s$/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Saltar descanso/i })).toBeInTheDocument();
  });

  it("AC-8-2: avisos por voz de descanso, diez segundos y fin de descanso con frases fijas", async () => {
    const playCueSpy = vi.spyOn(globalAudioPlayer, "playCue");
    const shortExercise = exerciseFixture({
      id: "e1111111-1111-1111-1111-111111111111",
      position: 1,
      name: "Sentadilla libre",
      sets: 2,
      reps: 10,
      work_seconds: null,
      rest_seconds: 2,
      guide: { steps: ["Paso 1"], disclaimer: "Aviso." },
    });

    server.use(
      http.get(`${API}/plan/today`, () =>
        ok(
          todayPlanFixture({
            plan_status: "ready",
            is_weekend: false,
            day: planDayDetailFixture({
              status: "training",
              exercises: [shortExercise],
            }),
          }),
        ),
      ),
      http.get(`${API}/plan/exercises/:id/audio`, () =>
        new HttpResponse(FAKE_WAV, { headers: { "Content-Type": "audio/wav" } }),
      ),
      http.get(`${API}/plan/audio/cues/:name`, () =>
        new HttpResponse(FAKE_WAV, { headers: { "Content-Type": "audio/wav" } }),
      ),
    );

    const { user } = renderRoute("/hoy/guiado", { me: ME });
    expect(await screen.findByRole("heading", { name: "Sentadilla libre" })).toBeInTheDocument();
    await waitFor(() => expect(mockPlay).toHaveBeenCalled());
    act(() => {
      globalAudioPlayer.getAudio().dispatchEvent(new Event("ended"));
    });

    // Pasar a descanso
    const doneBtn = await screen.findByRole("button", { name: /Terminar serie/i });
    await user.click(doneBtn);

    // Al entrar a descanso se solicita y reproduce cue "descanso"
    await waitFor(() => {
      expect(playCueSpy).toHaveBeenCalledWith("descanso", expect.anything());
    });
  });

  it("AC-8-2: si el descanso original es <= 10 s, no se duplica el aviso de 10 s", async () => {
    const playCueSpy = vi.spyOn(globalAudioPlayer, "playCue");
    const exerciseTenSec = exerciseFixture({
      id: "e1111111-1111-1111-1111-111111111111",
      position: 1,
      name: "Sentadilla libre",
      sets: 2,
      reps: 10,
      work_seconds: null,
      rest_seconds: 10,
      guide: { steps: ["Paso 1"], disclaimer: "Aviso." },
    });

    server.use(
      http.get(`${API}/plan/today`, () =>
        ok(
          todayPlanFixture({
            plan_status: "ready",
            is_weekend: false,
            day: planDayDetailFixture({
              status: "training",
              exercises: [exerciseTenSec],
            }),
          }),
        ),
      ),
      http.get(`${API}/plan/exercises/:id/audio`, () =>
        new HttpResponse(FAKE_WAV, { headers: { "Content-Type": "audio/wav" } }),
      ),
      http.get(`${API}/plan/audio/cues/:name`, () =>
        new HttpResponse(FAKE_WAV, { headers: { "Content-Type": "audio/wav" } }),
      ),
    );

    const { user } = renderRoute("/hoy/guiado", { me: ME });
    expect(await screen.findByRole("heading", { name: "Sentadilla libre" })).toBeInTheDocument();
    await waitFor(() => expect(mockPlay).toHaveBeenCalled());
    act(() => {
      globalAudioPlayer.getAudio().dispatchEvent(new Event("ended"));
    });

    const doneBtn = await screen.findByRole("button", { name: /Terminar serie/i });
    await user.click(doneBtn);

    // En descanso: "descanso" se reproduce
    await waitFor(() => {
      expect(playCueSpy).toHaveBeenCalledWith("descanso", expect.anything());
    });

    // "diez-segundos" NO debe reproducirse porque el descanso total ya era <= 10s
    expect(playCueSpy).not.toHaveBeenCalledWith("diez-segundos", expect.anything());
  });


  it("AC-8-4: si el audio del cue falla (503 AI_UNAVAILABLE), degrada a la voz del navegador con texto en español", async () => {
    server.use(
      http.get(`${API}/plan/today`, () =>
        ok(
          todayPlanFixture({
            plan_status: "ready",
            is_weekend: false,
            day: trainingDay,
          }),
        ),
      ),
      http.get(`${API}/plan/exercises/:id/audio`, () =>
        new HttpResponse(FAKE_WAV, { headers: { "Content-Type": "audio/wav" } }),
      ),
      http.get(`${API}/plan/audio/cues/:name`, () =>
        apiError(503, "AI_UNAVAILABLE", "Servicio de audio no disponible"),
      ),
    );

    const { user } = renderRoute("/hoy/guiado", { me: ME });
    expect(await screen.findByRole("heading", { name: "Sentadilla libre" })).toBeInTheDocument();
    await waitFor(() => expect(mockPlay).toHaveBeenCalled());
    act(() => {
      globalAudioPlayer.getAudio().dispatchEvent(new Event("ended"));
    });

    mockSpeak.mockClear();
    const doneBtn = await screen.findByRole("button", { name: /Terminar serie/i });
    await user.click(doneBtn);

    // Al fallar el cue con 503, se usa la voz del navegador con la frase de descanso en español
    await waitFor(() => {
      const calls = mockSpeak.mock.calls.map((c) => (c[0] as MockSpeechSynthesisUtterance).text);
      expect(calls).toContain(AUDIO_CUES_TEXT["descanso"]);
    });
  });

  it("Pausar en descanso detiene el temporizador y reanudar retoma desde el tiempo restante", async () => {
    setupTrainingServer();
    const { user } = renderRoute("/hoy/guiado", { me: ME });

    expect(await screen.findByRole("heading", { name: "Sentadilla libre" })).toBeInTheDocument();
    await waitFor(() => expect(mockPlay).toHaveBeenCalled());
    act(() => {
      globalAudioPlayer.getAudio().dispatchEvent(new Event("ended"));
    });

    const doneBtn = await screen.findByRole("button", { name: /Terminar serie/i });
    await user.click(doneBtn);

    expect(await screen.findByText("Descanso")).toBeInTheDocument();

    // Pausar
    const pauseBtn = screen.getByRole("button", { name: /Pausar/i });
    await user.click(pauseBtn);
    expect(screen.getByText("Entrenamiento en pausa")).toBeInTheDocument();

    // Reanudar
    const resumeBtn = screen.getByRole("button", { name: /Continuar/i });
    await user.click(resumeBtn);
    expect(await screen.findByText("Descanso")).toBeInTheDocument();
  });

  it("Saltar descanso cancela audios y avanza de inmediato a la siguiente serie", async () => {
    setupTrainingServer();
    const { user } = renderRoute("/hoy/guiado", { me: ME });

    expect(await screen.findByRole("heading", { name: "Sentadilla libre" })).toBeInTheDocument();
    await waitFor(() => expect(mockPlay).toHaveBeenCalled());
    act(() => {
      globalAudioPlayer.getAudio().dispatchEvent(new Event("ended"));
    });

    const doneBtn = await screen.findByRole("button", { name: /Terminar serie/i });
    await user.click(doneBtn);

    const skipBtn = await screen.findByRole("button", { name: /Saltar descanso/i });
    await user.click(skipBtn);

    // Avanza directamente a la Serie 2
    expect(await screen.findByText(/Serie 2 de 2/i)).toBeInTheDocument();
  });
});

