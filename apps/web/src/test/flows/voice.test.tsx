import { screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { globalAudioPlayer } from "../../features/voice/AudioPlayer";
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

describe("HU 3, HU 4 y HU 5 — Audio de ejercicios (síntesis de voz)", () => {
  let mockPlay: ReturnType<typeof vi.fn>;
  let mockPause: ReturnType<typeof vi.fn>;
  let mockLoad: ReturnType<typeof vi.fn>;
  let mockCreateObjectURL: ReturnType<typeof vi.fn>;
  let mockRevokeObjectURL: ReturnType<typeof vi.fn>;

  const FAKE_WAV = new Uint8Array([82, 73, 70, 70, 36, 0, 0, 0, 87, 65, 86, 69]); // RIFF...WAVE

  beforeEach(() => {
    localStorage.clear();
    globalAudioPlayer.stop();
    globalAudioPlayer.clearCache();

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
  });

  afterEach(() => {
    globalAudioPlayer.stop();
    globalAudioPlayer.clearCache();
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

  it("AC-3-1: al pulsar «Escuchar» se pide el audio y se llama a play", async () => {
    const { exercise } = setupExercise();
    const { user } = renderRoute(`/hoy?ejercicio=${exercise.id}`, { me: ME });

    expect(await screen.findByRole("dialog")).toBeInTheDocument();

    const listenBtn = screen.getByRole("button", { name: "Escuchar" });
    expect(listenBtn).toBeInTheDocument();

    await user.click(listenBtn);

    expect(sent("GET", `/plan/exercises/${exercise.id}/audio`)).toHaveLength(1);
    expect(mockPlay).toHaveBeenCalledTimes(1);
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

  it("error 503 AI_UNAVAILABLE muestra mensaje en español y permite reintentar", async () => {
    const exercise = exerciseFixture({ id: "e-fail" });
    let attempts = 0;

    server.use(
      http.get(
        `${API}/plan/today`,
        () => ok(todayPlanFixture({ day: planDayDetailFixture({ exercises: [exercise] }) })),
      ),
      http.get(`${API}/plan/exercises/${exercise.id}/audio`, () => {
        attempts += 1;
        if (attempts === 1) {
          return apiError(503, "AI_UNAVAILABLE", "El servicio de IA no está disponible.");
        }
        return new HttpResponse(FAKE_WAV, { headers: { "Content-Type": "audio/wav" } });
      }),
    );

    const { user } = renderRoute(`/hoy?ejercicio=${exercise.id}`, { me: ME });
    expect(await screen.findByRole("dialog")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Escuchar" }));

    // Muestra banner de error en español
    expect(await screen.findByText("No pudimos generar el audio")).toBeInTheDocument();
    expect(screen.getByText("El servicio de IA no está disponible.")).toBeInTheDocument();

    // Reintentar
    const retryBtn = screen.getByRole("button", { name: "Reintentar" });
    await user.click(retryBtn);

    // Segundo intento exitoso
    expect(attempts).toBe(2);
    expect(mockPlay).toHaveBeenCalledTimes(1);
    expect(screen.queryByText("No pudimos generar el audio")).not.toBeInTheDocument();
  });
});
