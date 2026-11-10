import { useCallback, useEffect, useRef, useState, useSyncExternalStore } from "react";
import type { PlanExercise } from "../../shared/api/types";
import { globalAudioPlayer, type AudioPlayer, type AudioPlayerState } from "./AudioPlayer";
import {
  buildExerciseFallbackPhrases,
  globalBrowserFallback,
  type BrowserFallback,
} from "./BrowserFallback";
import type { PlaybackRate } from "./playbackRate";

export const AI_AUDIO_TIMEOUT_MS = 15000;

export function useExerciseAudio(
  exerciseOrId: PlanExercise | string | null,
  exerciseArg?: PlanExercise | null,
  player: AudioPlayer = globalAudioPlayer,
  fallback: BrowserFallback = globalBrowserFallback,
) {
  const exercise =
    typeof exerciseOrId === "object" ? exerciseOrId : exerciseArg ?? null;
  const exerciseId =
    typeof exerciseOrId === "string" ? exerciseOrId : exerciseOrId?.id ?? null;

  const [engine, setEngine] = useState<"ai" | "browser">("ai");
  const [isUnavailable, setIsUnavailable] = useState(false);
  const [isWaitingAi, setIsWaitingAi] = useState(false);
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const playerSnapshot = useSyncExternalStore(
    player.subscribe,
    player.getSnapshot,
    player.getSnapshot,
  );

  const fallbackSnapshot = useSyncExternalStore(
    fallback.subscribe,
    fallback.getSnapshot,
    fallback.getSnapshot,
  );

  const activeSnapshot = engine === "browser" ? fallbackSnapshot : playerSnapshot;
  const isCurrent = Boolean(exerciseId && activeSnapshot.exerciseId === exerciseId);

  let state: AudioPlayerState = "idle";
  if (isUnavailable) {
    state = "unavailable";
  } else if (isWaitingAi || (engine === "ai" && isCurrent && playerSnapshot.state === "loading")) {
    state = "loading";
  } else if (isCurrent) {
    state = activeSnapshot.state;
  }

  const error = isCurrent ? activeSnapshot.error : null;
  const isLoading = state === "loading";
  const isPlaying = state === "playing";
  const isPaused = state === "paused";
  const hasAudio = isPlaying || isPaused;
  const isFallback = engine === "browser";

  const clearAiTimeout = useCallback(() => {
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
      timeoutRef.current = null;
    }
  }, []);

  useEffect(() => {
    return () => {
      clearAiTimeout();
    };
  }, [clearAiTimeout]);

  const startFallback = useCallback(
    async (targetExerciseId: string) => {
      clearAiTimeout();
      setIsWaitingAi(false);
      player.stop();

      if (!fallback.isAvailable()) {
        setEngine("browser");
        setIsUnavailable(true);
        return;
      }

      setEngine("browser");
      setIsUnavailable(false);
      const phrases = exercise
        ? buildExerciseFallbackPhrases(exercise)
        : [targetExerciseId];
      await fallback.play(targetExerciseId, phrases);
    },
    [clearAiTimeout, exercise, fallback, player],
  );

  const play = useCallback(async () => {
    if (!exerciseId || isLoading) return;

    // Si ya estamos en modo fallback o la voz IA no está disponible
    if (engine === "browser") {
      await startFallback(exerciseId);
      return;
    }

    // Modo IA: verificar si ya está en caché para reproducir al instante
    if (player.isCached(exerciseId)) {
      await player.play(exerciseId);
      return;
    }

    // Si no está en caché, intentamos IA con temporizador de 15 segundos (AC-6-1)
    setIsWaitingAi(true);
    let didTimeout = false;

    clearAiTimeout();
    timeoutRef.current = setTimeout(() => {
      didTimeout = true;
      startFallback(exerciseId);
    }, AI_AUDIO_TIMEOUT_MS);

    try {
      await player.play(exerciseId);
    } catch {
      // Ignorado, el snapshot reflejará error
    } finally {
      setIsWaitingAi(false);
    }

    // Si ya se activó el timeout, no procesar el resultado de la IA
    if (didTimeout) {
      return;
    }

    clearAiTimeout();

    // Si la IA falló (ej. 503 AI_UNAVAILABLE o error de red), conmutar a respaldo del navegador (AC-6-1)
    if (player.getSnapshot().state === "error") {
      await startFallback(exerciseId);
    }
  }, [clearAiTimeout, engine, exerciseId, isLoading, player, startFallback]);

  const pause = useCallback(() => {
    if (engine === "browser") {
      fallback.pause();
    } else if (isCurrent) {
      player.pause();
    }
  }, [engine, fallback, isCurrent, player]);

  const resume = useCallback(async () => {
    if (engine === "browser") {
      await fallback.resume();
    } else if (isCurrent) {
      await player.resume();
    }
  }, [engine, fallback, isCurrent, player]);

  const restart = useCallback(async () => {
    if (engine === "browser") {
      await fallback.restart();
    } else if (isCurrent) {
      await player.restart();
    }
  }, [engine, fallback, isCurrent, player]);

  const stop = useCallback(() => {
    clearAiTimeout();
    setIsWaitingAi(false);
    player.stop();
    fallback.stop();
    setEngine("ai");
    setIsUnavailable(false);
  }, [clearAiTimeout, fallback, player]);

  const setRate = useCallback(
    (rate: PlaybackRate) => {
      player.setRate(rate);
      fallback.setRate(rate);
    },
    [fallback, player],
  );

  return {
    state,
    isLoading,
    isPlaying,
    isPaused,
    isUnavailable,
    hasAudio,
    engine,
    isFallback,
    rate: activeSnapshot.rate,
    error,
    play,
    pause,
    resume,
    restart,
    stop,
    setRate,
  };
}
