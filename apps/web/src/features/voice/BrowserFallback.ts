import type { AudioPlayerSnapshot, AudioPlayerState } from "./AudioPlayer";
import {
  DEFAULT_PLAYBACK_RATE,
  loadPlaybackRate,
  savePlaybackRate,
  type PlaybackRate,
} from "./playbackRate";

export function getSpanishVoices(): SpeechSynthesisVoice[] {
  if (typeof window === "undefined" || !("speechSynthesis" in window)) {
    return [];
  }
  try {
    return window.speechSynthesis.getVoices().filter((v) => {
      const lang = (v.lang || "").toLowerCase().replace("_", "-");
      return lang.startsWith("es");
    });
  } catch {
    return [];
  }
}

export function buildExerciseFallbackPhrases(exercise: {
  name: string;
  guide: { steps: string[]; disclaimer: string };
}): string[] {
  const phrases: string[] = [exercise.name.trim()];
  exercise.guide.steps.forEach((step, idx) => {
    const clean = step.trim();
    if (clean) {
      const prefix = /^paso\s*\d+/i.test(clean) ? "" : `Paso ${idx + 1}: `;
      phrases.push(`${prefix}${clean}`);
    }
  });
  if (exercise.guide.disclaimer.trim()) {
    phrases.push(exercise.guide.disclaimer.trim());
  }
  return phrases;
}

export class BrowserFallback {
  private state: AudioPlayerState = "idle";
  private error: Error | null = null;
  private rate: PlaybackRate = DEFAULT_PLAYBACK_RATE;
  private phrases: string[] = [];
  private currentPhraseIndex = 0;
  private currentExerciseId: string | null = null;
  private listeners = new Set<(snapshot: AudioPlayerSnapshot) => void>();
  private isCancellingExplicitly = false;
  private snapshot: AudioPlayerSnapshot;

  constructor() {
    this.rate = loadPlaybackRate();
    this.snapshot = {
      state: "idle",
      exerciseId: null,
      error: null,
      rate: this.rate,
    };

    if (typeof window !== "undefined" && "speechSynthesis" in window) {
      try {
        window.speechSynthesis.addEventListener("voiceschanged", () => {
          // Escuchar carga asíncrona de voces del sistema
          this.notify();
        });
      } catch {
        // Ignorar si el navegador no admite addEventListener en speechSynthesis
      }
    }
  }

  public isAvailable(): boolean {
    if (
      typeof window === "undefined" ||
      !("speechSynthesis" in window) ||
      typeof SpeechSynthesisUtterance === "undefined"
    ) {
      return false;
    }
    const voices = getSpanishVoices();
    return voices.length > 0;
  }

  public getSelectedVoice(): SpeechSynthesisVoice | null {
    const voices = getSpanishVoices();
    if (!voices.length) return null;
    return voices.find((v) => v.default) ?? voices[0] ?? null;
  }

  private updateSnapshot(): void {
    this.snapshot = {
      state: this.state,
      exerciseId: this.currentExerciseId,
      error: this.error,
      rate: this.rate,
    };
  }

  private setState(state: AudioPlayerState, error: Error | null = null): void {
    this.state = state;
    if (error !== null || state !== "error") {
      this.error = error;
    }
    this.updateSnapshot();
    this.notify();
  }

  private notify(): void {
    const snapshot = this.getSnapshot();
    for (const listener of this.listeners) {
      try {
        listener(snapshot);
      } catch (err) {
        console.error("BrowserFallback listener error:", err);
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

  public async play(exerciseId: string, phrases: string[]): Promise<void> {
    if (!this.isAvailable()) {
      this.currentExerciseId = exerciseId;
      this.setState("unavailable", new Error("No hay voces en español disponibles en el dispositivo."));
      return;
    }

    if (this.currentExerciseId === exerciseId && this.state === "playing") {
      return;
    }

    this.stop();

    this.currentExerciseId = exerciseId;
    this.phrases = phrases.filter((p) => Boolean(p && p.trim()));
    this.currentPhraseIndex = 0;

    if (this.phrases.length === 0) {
      this.setState("idle");
      return;
    }

    this.setState("playing");
    this.speakCurrentPhrase();
  }

  private speakCurrentPhrase(): void {
    if (typeof window === "undefined" || !("speechSynthesis" in window)) return;
    if (this.currentPhraseIndex >= this.phrases.length) {
      this.setState("paused");
      return;
    }

    const text = this.phrases[this.currentPhraseIndex]!;
    const utterance = new SpeechSynthesisUtterance(text);
    const voice = this.getSelectedVoice();
    if (voice) {
      utterance.voice = voice;
      utterance.lang = voice.lang;
    } else {
      utterance.lang = "es-ES";
    }
    utterance.rate = this.rate;

    utterance.onend = () => {
      if (this.isCancellingExplicitly) return;
      this.currentPhraseIndex++;
      if (this.currentPhraseIndex < this.phrases.length) {
        this.speakCurrentPhrase();
      } else {
        this.setState("paused");
      }
    };

    utterance.onerror = (event: any) => {
      if (this.isCancellingExplicitly || event?.error === "canceled" || event?.error === "interrupted") {
        return;
      }
      this.setState("error", new Error("Ocurrió un error en la síntesis de voz del dispositivo."));
    };

    try {
      window.speechSynthesis.speak(utterance);
    } catch (err) {
      this.setState("error", err instanceof Error ? err : new Error("No se pudo iniciar la voz del navegador"));
    }
  }

  public pause(): void {
    this.isCancellingExplicitly = true;
    try {
      if (typeof window !== "undefined" && "speechSynthesis" in window) {
        window.speechSynthesis.cancel();
      }
    } finally {
      this.isCancellingExplicitly = false;
    }
    this.setState("paused");
  }

  public async resume(): Promise<void> {
    if (!this.currentExerciseId || this.phrases.length === 0) return;
    if (this.currentPhraseIndex >= this.phrases.length) {
      this.currentPhraseIndex = 0;
    }
    this.setState("playing");
    this.speakCurrentPhrase();
  }

  public async restart(): Promise<void> {
    if (!this.currentExerciseId || this.phrases.length === 0) return;
    this.isCancellingExplicitly = true;
    try {
      if (typeof window !== "undefined" && "speechSynthesis" in window) {
        window.speechSynthesis.cancel();
      }
    } finally {
      this.isCancellingExplicitly = false;
    }
    this.currentPhraseIndex = 0;
    this.setState("playing");
    this.speakCurrentPhrase();
  }

  public stop(): void {
    this.isCancellingExplicitly = true;
    try {
      if (typeof window !== "undefined" && "speechSynthesis" in window) {
        window.speechSynthesis.cancel();
      }
    } finally {
      this.isCancellingExplicitly = false;
    }
    this.currentPhraseIndex = 0;
    this.currentExerciseId = null;
    this.phrases = [];
    this.setState("idle", null);
  }

  public setRate(rate: PlaybackRate): void {
    this.rate = rate;
    savePlaybackRate(rate);
    this.updateSnapshot();
    this.notify();
    if (this.state === "playing") {
      this.isCancellingExplicitly = true;
      try {
        if (typeof window !== "undefined" && "speechSynthesis" in window) {
          window.speechSynthesis.cancel();
        }
      } finally {
        this.isCancellingExplicitly = false;
      }
      this.speakCurrentPhrase();
    }
  }

  public getCurrentPhraseIndex(): number {
    return this.currentPhraseIndex;
  }

  public getPhrases(): readonly string[] {
    return this.phrases;
  }

  public getCurrentExerciseId(): string | null {
    return this.currentExerciseId;
  }
}

export const globalBrowserFallback = new BrowserFallback();
