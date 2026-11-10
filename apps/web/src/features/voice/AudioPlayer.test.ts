import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AudioPlayer } from "./AudioPlayer";
import * as voiceApi from "./api";

describe("AudioPlayer", () => {
  let player: AudioPlayer;
  let mockPlay: ReturnType<typeof vi.fn>;
  let mockPause: ReturnType<typeof vi.fn>;
  let mockLoad: ReturnType<typeof vi.fn>;
  let mockCreateObjectURL: ReturnType<typeof vi.fn>;
  let mockRevokeObjectURL: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    localStorage.clear();
    mockPlay = vi.fn().mockImplementation(async function (this: HTMLAudioElement) {
      this.dispatchEvent(new Event("play"));
      return Promise.resolve();
    });
    mockPause = vi.fn().mockImplementation(function (this: HTMLAudioElement) {
      this.dispatchEvent(new Event("pause"));
    });
    mockLoad = vi.fn();
    mockCreateObjectURL = vi.fn((blob: Blob) => `blob:http://localhost/${blob.size}`);
    mockRevokeObjectURL = vi.fn();

    window.HTMLMediaElement.prototype.play = mockPlay as unknown as () => Promise<void>;
    window.HTMLMediaElement.prototype.pause = mockPause as unknown as () => void;
    window.HTMLMediaElement.prototype.load = mockLoad as unknown as () => void;
    window.URL.createObjectURL = mockCreateObjectURL as unknown as (obj: Blob | MediaSource) => string;
    window.URL.revokeObjectURL = mockRevokeObjectURL as unknown as (url: string) => void;

    player = new AudioPlayer(2); // max 2 items to test LRU eviction easily
  });

  afterEach(() => {
    player.stop();
    player.clearCache();
    vi.restoreAllMocks();
  });

  it("arranca en estado idle", () => {
    const snap = player.getSnapshot();
    expect(snap.state).toBe("idle");
    expect(snap.exerciseId).toBeNull();
    expect(snap.error).toBeNull();
    expect(snap.rate).toBe(1);
  });

  it("AC-3-1: play(exerciseId) pide el audio, asigna src y llama a play", async () => {
    const fakeBlob = new Blob(["RIFFfake"], { type: "audio/wav" });
    const fetchSpy = vi.spyOn(voiceApi, "fetchExerciseAudio").mockResolvedValue(fakeBlob);

    await player.play("ex-1");

    expect(fetchSpy).toHaveBeenCalledWith("ex-1", expect.any(AbortSignal));
    expect(mockCreateObjectURL).toHaveBeenCalledWith(fakeBlob);
    expect(mockPlay).toHaveBeenCalledTimes(1);
    expect(player.getSnapshot().state).toBe("playing");
    expect(player.getSnapshot().exerciseId).toBe("ex-1");
  });

  it("AC-3-2: mientras se carga no lanza peticiones duplicadas ante clics repetidos", async () => {
    let resolveBlob!: (blob: Blob) => void;
    const pendingPromise = new Promise<Blob>((resolve) => {
      resolveBlob = resolve;
    });
    const fetchSpy = vi.spyOn(voiceApi, "fetchExerciseAudio").mockReturnValue(pendingPromise);

    const firstPlay = player.play("ex-1");
    expect(player.getSnapshot().state).toBe("loading");

    // Segundo clic concurrente con el mismo ejercicio
    const secondPlay = player.play("ex-1");

    expect(fetchSpy).toHaveBeenCalledTimes(1);

    resolveBlob(new Blob(["wav"]));
    await Promise.all([firstPlay, secondPlay]);

    expect(fetchSpy).toHaveBeenCalledTimes(1);
    expect(player.getSnapshot().state).toBe("playing");
  });

  it("AC-3-3: la segunda reproducción del mismo ejercicio usa la caché en memoria", async () => {
    const fakeBlob = new Blob(["RIFFfake"], { type: "audio/wav" });
    const fetchSpy = vi.spyOn(voiceApi, "fetchExerciseAudio").mockResolvedValue(fakeBlob);

    await player.play("ex-1");
    expect(fetchSpy).toHaveBeenCalledTimes(1);

    // Pausar y volver a reproducir el mismo ejercicio
    player.pause();
    await player.play("ex-1");

    // No debe haber llamado a la API una segunda vez
    expect(fetchSpy).toHaveBeenCalledTimes(1);
  });

  it("AC-3-5: reproducir otro ejercicio detiene el anterior (un solo elemento de audio)", async () => {
    const fakeBlob = new Blob(["RIFFfake"], { type: "audio/wav" });
    vi.spyOn(voiceApi, "fetchExerciseAudio").mockResolvedValue(fakeBlob);

    await player.play("ex-1");
    expect(player.getSnapshot().exerciseId).toBe("ex-1");

    await player.play("ex-2");
    expect(mockPause).toHaveBeenCalled();
    expect(player.getSnapshot().exerciseId).toBe("ex-2");
    expect(player.getSnapshot().state).toBe("playing");
  });

  it("AC-4-1 y AC-4-2: pausa, reanudar y repetir", async () => {
    const fakeBlob = new Blob(["RIFFfake"], { type: "audio/wav" });
    vi.spyOn(voiceApi, "fetchExerciseAudio").mockResolvedValue(fakeBlob);

    await player.play("ex-1");
    expect(player.getSnapshot().state).toBe("playing");

    player.pause();
    expect(player.getSnapshot().state).toBe("paused");
    expect(mockPause).toHaveBeenCalled();

    await player.resume();
    expect(player.getSnapshot().state).toBe("playing");

    await player.restart();
    const audio = player.getAudio();
    expect(audio.currentTime).toBe(0);
    expect(player.getSnapshot().state).toBe("playing");
  });

  it("AC-5-1: cambio de velocidad se aplica con preservesPitch sin reiniciar el audio", async () => {
    const fakeBlob = new Blob(["RIFFfake"], { type: "audio/wav" });
    vi.spyOn(voiceApi, "fetchExerciseAudio").mockResolvedValue(fakeBlob);

    await player.play("ex-1");
    const audio = player.getAudio();
    audio.currentTime = 5.0;

    player.setRate(1.25);

    expect(audio.playbackRate).toBe(1.25);
    expect(audio.preservesPitch).toBe(true);
    expect(audio.currentTime).toBe(5.0); // no reinició posición
    expect(player.getSnapshot().rate).toBe(1.25);
  });

  it("desaloja entradas antiguas llamando a URL.revokeObjectURL al superar el límite de caché", async () => {
    const fakeBlob = new Blob(["RIFFfake"], { type: "audio/wav" });
    vi.spyOn(voiceApi, "fetchExerciseAudio").mockResolvedValue(fakeBlob);

    await player.play("ex-1");
    await player.play("ex-2");
    expect(mockRevokeObjectURL).not.toHaveBeenCalled();

    // Tercer ejercicio sobre límite de 2
    await player.play("ex-3");
    expect(mockRevokeObjectURL).toHaveBeenCalledTimes(1);
    expect(player.isCached("ex-1")).toBe(false);
    expect(player.isCached("ex-2")).toBe(true);
    expect(player.isCached("ex-3")).toBe(true);
  });

  it("maneja errores de la API pasando a estado error", async () => {
    vi.spyOn(voiceApi, "fetchExerciseAudio").mockRejectedValue(new Error("503 AI_UNAVAILABLE"));

    await player.play("ex-error");
    expect(player.getSnapshot().state).toBe("error");
    expect(player.getSnapshot().error?.message).toContain("503");
  });
});
