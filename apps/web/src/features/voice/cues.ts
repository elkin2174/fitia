/**
 * Catálogo y utilidades de reproducción para frases fijas de audio (cues) (MVP 2 - HU 8).
 *
 * Catálogo cerrado:
 * - "descanso": "Descansa y recupera el aliento."
 * - "diez-segundos": "Quedan diez segundos."
 * - "fin-descanso": "Termina el descanso. ¡A seguir!"
 * - "fin-rutina": "Terminaste la rutina de hoy. ¡Buen trabajo!"
 *
 * AC-8-2: Avisos por voz generados por IA y cacheados.
 * AC-8-4: Si el audio de una frase falla, se usa la voz del navegador en español.
 */
import { globalAudioPlayer, type AudioPlayer } from "./AudioPlayer";
import { globalBrowserFallback, type BrowserFallback } from "./BrowserFallback";

export const AUDIO_CUES_TEXT = {
  descanso: "Descansa y recupera el aliento.",
  "diez-segundos": "Quedan diez segundos.",
  "fin-descanso": "Termina el descanso. ¡A seguir!",
  "fin-rutina": "Terminaste la rutina de hoy. ¡Buen trabajo!",
} as const;

export type AudioCueName = keyof typeof AUDIO_CUES_TEXT;

export const ALL_CUE_NAMES: readonly AudioCueName[] = [
  "descanso",
  "diez-segundos",
  "fin-descanso",
  "fin-rutina",
];

export function isAudioCueName(name: string): name is AudioCueName {
  return name in AUDIO_CUES_TEXT;
}

/**
 * Emite una locución con la síntesis de voz del navegador.
 */
export function speakWithBrowser(
  text: string,
  fallback: BrowserFallback = globalBrowserFallback,
): Promise<void> {
  return new Promise((resolve) => {
    if (
      typeof window === "undefined" ||
      !("speechSynthesis" in window) ||
      !window.speechSynthesis ||
      typeof SpeechSynthesisUtterance === "undefined"
    ) {
      resolve();
      return;
    }
    try {
      const utterance = new SpeechSynthesisUtterance(text);
      const voice = fallback.getSelectedVoice();
      if (voice) {
        utterance.voice = voice;
        utterance.lang = voice.lang;
      } else {
        utterance.lang = "es-ES";
      }
      utterance.rate = fallback.getSnapshot().rate ?? 1;
      utterance.onend = () => resolve();
      utterance.onerror = () => resolve();
      window.speechSynthesis.speak(utterance);
    } catch {
      resolve();
    }
  });
}

/**
 * Reproduce un cue con IA (AudioPlayer) y degrada a la voz del navegador si falla (AC-8-2, AC-8-4).
 * Devuelve una promesa que resuelve cuando la reproducción termina efectivamente.
 */
export async function playCueWithFallback(
  cueName: AudioCueName,
  player: AudioPlayer = globalAudioPlayer,
  fallback: BrowserFallback = globalBrowserFallback,
  signal?: AbortSignal,
): Promise<void> {
  if (signal?.aborted) return;

  // 1. Intentar reproducir con la IA (AudioPlayer)
  try {
    let cleanup: (() => void) | undefined;

    const endedPromise = new Promise<void>((resolve) => {
      cleanup = player.onEnded(() => {
        resolve();
      });
    });

    const abortHandler = () => {
      cleanup?.();
      player.stop();
    };
    signal?.addEventListener("abort", abortHandler, { once: true });

    try {
      await player.playCue(cueName, signal);

      if (player.getSnapshot().state === "error") {
        throw new Error("AudioPlayer error state");
      }

      // Esperar a que el audio termine
      await endedPromise;
    } finally {
      cleanup?.();
      signal?.removeEventListener("abort", abortHandler);
    }
  } catch {
    if (signal?.aborted) return;
    // 2. AC-8-4: Si el audio de la IA falla, se usa la voz del navegador
    player.stop();
    await speakWithBrowser(AUDIO_CUES_TEXT[cueName], fallback);
  }
}

/**
 * Precarga en segundo plano los 4 audios de las frases fijas.
 */
export async function preloadCues(
  player: AudioPlayer = globalAudioPlayer,
  signal?: AbortSignal,
): Promise<void> {
  const tasks = ALL_CUE_NAMES.map((name) => player.preloadCue(name, signal));
  await Promise.allSettled(tasks);
}
