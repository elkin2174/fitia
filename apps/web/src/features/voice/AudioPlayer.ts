import { fetchExerciseAudio } from "./api";
import {
  DEFAULT_PLAYBACK_RATE,
  loadPlaybackRate,
  savePlaybackRate,
  type PlaybackRate,
} from "./playbackRate";

export type AudioPlayerState = "idle" | "loading" | "playing" | "paused" | "error" | "unavailable";

export interface AudioPlayerSnapshot {
  state: AudioPlayerState;
  exerciseId: string | null;
  error: Error | null;
  rate: PlaybackRate;
}

interface CachedAudio {
  blob: Blob;
  url: string;
}

export class AudioPlayer {
  private audioElement: HTMLAudioElement | null = null;
  private cache = new Map<string, CachedAudio>();
  private readonly maxCacheSize: number;
  private currentExerciseId: string | null = null;
  private state: AudioPlayerState = "idle";
  private error: Error | null = null;
  private rate: PlaybackRate = DEFAULT_PLAYBACK_RATE;
  private listeners = new Set<(snapshot: AudioPlayerSnapshot) => void>();
  private activeAbortController: AbortController | null = null;
  private snapshot: AudioPlayerSnapshot;

  constructor(maxCacheSize = 50) {
    this.maxCacheSize = maxCacheSize;
    this.rate = loadPlaybackRate();
    this.snapshot = {
      state: "idle",
      exerciseId: null,
      error: null,
      rate: this.rate,
    };
  }

  private updateSnapshot(): void {
    this.snapshot = {
      state: this.state,
      exerciseId: this.currentExerciseId,
      error: this.error,
      rate: this.rate,
    };
  }

  public getAudio(): HTMLAudioElement {
    if (!this.audioElement && typeof window !== "undefined") {
      this.audioElement = new Audio();
      this.setupAudioListeners(this.audioElement);
    }
    return this.audioElement!;
  }

  private setupAudioListeners(audio: HTMLAudioElement): void {
    audio.addEventListener("play", () => {
      this.setState("playing");
    });

    audio.addEventListener("pause", () => {
      if (this.state === "playing") {
        this.setState("paused");
      }
    });

    audio.addEventListener("ended", () => {
      this.setState("paused");
    });

    audio.addEventListener("error", () => {
      this.error = new Error("Error en la reproducción de audio");
      this.setState("error");
    });
  }

  private setState(state: AudioPlayerState, error: Error | null = null): void {
    this.state = state;
    if (error !== null || state !== "error") {
      this.error = error;
    }
    this.updateSnapshot();
    this.updateSnapshot();
    this.notify();
  }

  private notify(): void {
    const snapshot = this.getSnapshot();
    for (const listener of this.listeners) {
      try {
        listener(snapshot);
      } catch (err) {
        console.error("AudioPlayer listener error:", err);
      }
    }
  }

  public getSnapshot = (): AudioPlayerSnapshot => {
    return this.snapshot;
  };

  public subscribe = (listener: (snapshot: AudioPlayerSnapshot) => void): (() => void) => {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  };

  public async play(exerciseId: string): Promise<void> {
    // Si ya estamos cargando este mismo ejercicio, ignorar clic duplicado (AC-3-2)
    if (this.state === "loading" && this.currentExerciseId === exerciseId) {
      return;
    }

    // Detener cualquier audio previo antes de arrancar uno nuevo (AC-3-5)
    if (this.currentExerciseId && this.currentExerciseId !== exerciseId) {
      this.stop();
    }

    // Cancelar cualquier petición HTTP pendiente anterior
    if (this.activeAbortController) {
      this.activeAbortController.abort();
      this.activeAbortController = null;
    }

    this.currentExerciseId = exerciseId;

    // Verificar caché en memoria de proceso (AC-3-3)
    let cached = this.cache.get(exerciseId);

    if (!cached) {
      this.setState("loading", null);
      const controller = new AbortController();
      this.activeAbortController = controller;

      try {
        const blob = await fetchExerciseAudio(exerciseId, controller.signal);
        const url = URL.createObjectURL(blob);
        cached = { blob, url };

        // Desalojo LRU si superamos el tamaño máximo
        if (this.cache.size >= this.maxCacheSize) {
          const firstKey = this.cache.keys().next().value;
          if (firstKey) {
            const evicted = this.cache.get(firstKey);
            if (evicted) {
              URL.revokeObjectURL(evicted.url);
            }
            this.cache.delete(firstKey);
          }
        }
        this.cache.set(exerciseId, cached);
      } catch (err) {
        if ((err as Error)?.name === "AbortError") {
          return;
        }
        this.setState("error", err instanceof Error ? err : new Error(String(err)));
        return;
      } finally {
        if (this.activeAbortController === controller) {
          this.activeAbortController = null;
        }
      }
    }

    const audio = this.getAudio();
    if (audio.src !== cached.url) {
      audio.src = cached.url;
      audio.load();
    }
    audio.playbackRate = this.rate;
    // Preservar tono al cambiar velocidad (AC-5-1)
    try {
      (audio as HTMLAudioElement & { preservesPitch?: boolean }).preservesPitch = true;
    } catch {
      // Ignorar si el entorno no admite preservesPitch
    }

    try {
      this.setState("playing", null);
      await audio.play();
    } catch (playErr) {
      this.setState("error", playErr instanceof Error ? playErr : new Error("No se pudo iniciar la reproducción"));
    }
  }

  public pause(): void {
    if (this.audioElement) {
      this.audioElement.pause();
    }
    this.setState("paused");
  }

  public async resume(): Promise<void> {
    if (!this.audioElement || !this.currentExerciseId) return;

    if (this.audioElement.ended || (this.audioElement.duration && this.audioElement.currentTime >= this.audioElement.duration)) {
      this.audioElement.currentTime = 0;
    }
    this.audioElement.playbackRate = this.rate;
    try {
      (this.audioElement as HTMLAudioElement & { preservesPitch?: boolean }).preservesPitch = true;
    } catch {
      // Ignorar
    }
    this.setState("playing");
    try {
      await this.audioElement.play();
    } catch (err) {
      this.setState("error", err instanceof Error ? err : new Error("No se pudo reanudar el audio"));
    }
  }

  public async restart(): Promise<void> {
    if (!this.audioElement || !this.currentExerciseId) return;

    this.audioElement.currentTime = 0;
    this.audioElement.playbackRate = this.rate;
    try {
      (this.audioElement as HTMLAudioElement & { preservesPitch?: boolean }).preservesPitch = true;
    } catch {
      // Ignorar
    }
    this.setState("playing");
    try {
      await this.audioElement.play();
    } catch (err) {
      this.setState("error", err instanceof Error ? err : new Error("No se pudo reiniciar el audio"));
    }
  }

  public stop(): void {
    if (this.activeAbortController) {
      this.activeAbortController.abort();
      this.activeAbortController = null;
    }
    if (this.audioElement) {
      this.audioElement.pause();
      this.audioElement.currentTime = 0;
      this.audioElement.removeAttribute("src");
    }
    this.currentExerciseId = null;
    this.setState("idle", null);
  }

  public setRate(rate: PlaybackRate): void {
    this.rate = rate;
    savePlaybackRate(rate);
    if (this.audioElement) {
      this.audioElement.playbackRate = rate;
      try {
        (this.audioElement as HTMLAudioElement & { preservesPitch?: boolean }).preservesPitch = true;
      } catch {
        // Ignorar
      }
    }
    this.updateSnapshot();
    this.notify();
  }

  public clearCache(): void {
    for (const item of this.cache.values()) {
      URL.revokeObjectURL(item.url);
    }
    this.cache.clear();
  }

  public isCached(exerciseId: string): boolean {
    return this.cache.has(exerciseId);
  }

  public getCurrentExerciseId(): string | null {
    return this.currentExerciseId;
  }
}

// Instancia única compartida en toda la app (garantiza AC-3-5)
export const globalAudioPlayer = new AudioPlayer();
