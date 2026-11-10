import { useCallback, useEffect, useReducer, useRef, useState } from "react";
import type { PlanExercise } from "../../../shared/api/types";
import { formatSets, formatWork } from "../../../shared/lib/prescription";
import { globalAudioPlayer, type AudioPlayer } from "../AudioPlayer";
import {
  buildExerciseFallbackPhrases,
  globalBrowserFallback,
  type BrowserFallback,
} from "../BrowserFallback";
import {
  playCueWithFallback,
  preloadCues,
  speakWithBrowser,
} from "../cues";
import {
  createInitialGuidedState,
  guidedMachine,
  type GuidedExerciseConfig,
} from "./guidedMachine";

export { speakWithBrowser } from "../cues";

export interface UseGuidedSessionOptions {
  exercises: PlanExercise[];
  onRestTick?: (secondsRemaining: number) => void;
  onRestEnd?: () => void;
  player?: AudioPlayer;
  fallback?: BrowserFallback;
  autoStart?: boolean;
}

export function buildExerciseAnnouncement(exercise: PlanExercise): string {
  const setsText = formatSets(exercise.sets);
  const workText = formatWork(exercise.reps, exercise.work_seconds);
  return `${exercise.name.trim()}. ${setsText}, ${workText}.`;
}

export async function preloadExerciseAudios(
  exerciseIds: string[],
  player: AudioPlayer = globalAudioPlayer,
  maxConcurrency = 2,
  signal?: AbortSignal,
): Promise<void> {
  const queue = [...exerciseIds];
  const workers = Array.from({ length: Math.min(maxConcurrency, queue.length) }, async () => {
    while (queue.length > 0) {
      if (signal?.aborted) break;
      const id = queue.shift();
      if (!id) break;
      if (!player.isCached(id)) {
        await player.preload(id, signal);
      }
    }
  });
  await Promise.allSettled(workers);
}

export function useGuidedSession({
  exercises,
  onRestTick,
  onRestEnd,
  player = globalAudioPlayer,
  fallback = globalBrowserFallback,
  autoStart = true,
}: UseGuidedSessionOptions) {
  const exerciseConfigs: GuidedExerciseConfig[] = exercises.map((e) => ({
    id: e.id,
    name: e.name,
    sets: e.sets,
    reps: e.reps,
    work_seconds: e.work_seconds,
    rest_seconds: e.rest_seconds,
  }));

  const [state, dispatch] = useReducer(
    guidedMachine,
    exerciseConfigs,
    createInitialGuidedState,
  );

  const [timerSeconds, setTimerSeconds] = useState<number | null>(null);
  const [isLoadingAudio, setIsLoadingAudio] = useState(false);

  const sessionGenRef = useRef(0);
  const timerIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const unsubscribeEndedRef = useRef<(() => void) | null>(null);
  const preloadAbortRef = useRef<AbortController | null>(null);
  const restAbortRef = useRef<AbortController | null>(null);
  const pausedRemainingRef = useRef<number | null>(null);
  const targetEndTimeRef = useRef<number | null>(null);

  const currentExercise = exercises[state.exerciseIndex] ?? null;

  const clearTimer = useCallback(() => {
    if (timerIntervalRef.current) {
      clearInterval(timerIntervalRef.current);
      timerIntervalRef.current = null;
    }
  }, []);

  const stopActiveSpeechAndAudio = useCallback(() => {
    sessionGenRef.current++;
    pausedRemainingRef.current = null;
    targetEndTimeRef.current = null;
    if (restAbortRef.current) {
      restAbortRef.current.abort();
      restAbortRef.current = null;
    }
    clearTimer();
    if (unsubscribeEndedRef.current) {
      unsubscribeEndedRef.current();
      unsubscribeEndedRef.current = null;
    }
    if (typeof window !== "undefined" && "speechSynthesis" in window && window.speechSynthesis) {
      try {
        window.speechSynthesis.cancel();
      } catch {
        // Silencioso
      }
    }
    player.stop();
    fallback.stop();
    setIsLoadingAudio(false);
  }, [clearTimer, fallback, player]);

  // Precarga con concurrencia máxima de 2 sin bloquear la interfaz (AC-7-2, AC-8-2)
  useEffect(() => {
    if (exercises.length === 0) return;
    const controller = new AbortController();
    preloadAbortRef.current = controller;

    Promise.allSettled([
      preloadExerciseAudios(
        exercises.map((e) => e.id),
        player,
        2,
        controller.signal,
      ),
      preloadCues(player, controller.signal),
    ]).catch(() => {});

    return () => {
      controller.abort();
    };
  }, [exercises, player]);

  // Auto-inicio en idle si autoStart es verdadero
  useEffect(() => {
    if (exercises.length > 0 && state.exercises.length === 0) {
      dispatch({ type: "reset", exercises: exerciseConfigs });
      if (autoStart) {
        dispatch({ type: "start" });
      }
      return;
    }
    if (autoStart && state.status === "idle" && exercises.length > 0) {
      dispatch({ type: "start" });
    }
  }, [autoStart, exerciseConfigs, exercises.length, state.exercises.length, state.status]);

  // Manejo del estado announcing (AC-7-1)
  useEffect(() => {
    if (state.status !== "announcing" || !currentExercise) {
      return;
    }

    const currentGen = ++sessionGenRef.current;
    let isCancelled = false;

    async function runAnnouncement() {
      if (state.currentSet === 1) {
        // 1. Anuncio inicial del ejercicio (nombre, series y repeticiones o segundos)
        const announcementText = buildExerciseAnnouncement(currentExercise!);
        await speakWithBrowser(announcementText, fallback);
        if (isCancelled || sessionGenRef.current !== currentGen) return;

        // 2. Reproducir audio de los pasos con el audio de la HU 3 (con fallback HU 6)
        if (!player.isCached(currentExercise!.id)) {
          setIsLoadingAudio(true);
        }

        const handleAudioEnded = () => {
          if (isCancelled || sessionGenRef.current !== currentGen) return;
          if (unsubscribeEndedRef.current) {
            unsubscribeEndedRef.current();
            unsubscribeEndedRef.current = null;
          }
          dispatch({ type: "speechEnded" });
        };

        unsubscribeEndedRef.current = player.onEnded(handleAudioEnded);

        // Temporizador de respaldo de 15 segundos
        const fallbackTimer = setTimeout(async () => {
          if (isCancelled || sessionGenRef.current !== currentGen) return;
          player.stop();
          if (unsubscribeEndedRef.current) {
            unsubscribeEndedRef.current();
          }
          unsubscribeEndedRef.current = fallback.onEnded(handleAudioEnded);
          setIsLoadingAudio(false);
          const phrases = buildExerciseFallbackPhrases(currentExercise!);
          await fallback.play(currentExercise!.id, phrases);
        }, 15000);

        try {
          await player.play(currentExercise!.id);
          clearTimeout(fallbackTimer);
          setIsLoadingAudio(false);

          if (player.getSnapshot().state === "error") {
            if (unsubscribeEndedRef.current) {
              unsubscribeEndedRef.current();
            }
            unsubscribeEndedRef.current = fallback.onEnded(handleAudioEnded);
            const phrases = buildExerciseFallbackPhrases(currentExercise!);
            await fallback.play(currentExercise!.id, phrases);
          }
        } catch {
          clearTimeout(fallbackTimer);
          setIsLoadingAudio(false);
          if (unsubscribeEndedRef.current) {
            unsubscribeEndedRef.current();
          }
          unsubscribeEndedRef.current = fallback.onEnded(handleAudioEnded);
          const phrases = buildExerciseFallbackPhrases(currentExercise!);
          await fallback.play(currentExercise!.id, phrases);
        }
      } else {
        // Serie subsiguiente (Serie 2, Serie 3, etc.)
        const setText = `Serie ${state.currentSet} de ${state.totalSets}.`;
        await speakWithBrowser(setText, fallback);
        if (isCancelled || sessionGenRef.current !== currentGen) return;
        dispatch({ type: "speechEnded" });
      }
    }

    runAnnouncement();

    return () => {
      isCancelled = true;
      if (unsubscribeEndedRef.current) {
        unsubscribeEndedRef.current();
        unsubscribeEndedRef.current = null;
      }
      setIsLoadingAudio(false);
    };
  }, [currentExercise, fallback, player, state.announcementKey, state.currentSet, state.exerciseIndex, state.status, state.totalSets]);

  // Manejo del estado working (ejercicios por tiempo o repeticiones con cálculo basado en timestamp)
  useEffect(() => {
    if (state.status !== "working" || !currentExercise) {
      return;
    }

    clearTimer();

    if (currentExercise.work_seconds && currentExercise.work_seconds > 0) {
      const initialWork = pausedRemainingRef.current !== null
        ? pausedRemainingRef.current
        : currentExercise.work_seconds;
      pausedRemainingRef.current = null;

      setTimerSeconds(initialWork);
      targetEndTimeRef.current = Date.now() + initialWork * 1000;

      timerIntervalRef.current = setInterval(() => {
        const remaining = Math.max(0, Math.ceil((targetEndTimeRef.current! - Date.now()) / 1000));
        setTimerSeconds(remaining);
        if (remaining <= 0) {
          clearTimer();
          dispatch({ type: "timerEnded" });
        }
      }, 250);
    } else {
      setTimerSeconds(null);
    }

    return () => {
      clearTimer();
    };
  }, [clearTimer, currentExercise, state.currentSet, state.exerciseIndex, state.status]);

  // Manejo del estado resting (cuenta regresiva con avisos de voz HU 8 / AC-8-1, AC-8-2, AC-8-4)
  useEffect(() => {
    if (state.status !== "resting" || !currentExercise) {
      return;
    }

    clearTimer();
    const restController = new AbortController();
    restAbortRef.current = restController;

    const totalRest = currentExercise.rest_seconds || 30;
    const isResuming = pausedRemainingRef.current !== null;
    const initialRemaining = isResuming ? pausedRemainingRef.current! : totalRest;
    pausedRemainingRef.current = null;

    setTimerSeconds(initialRemaining);
    onRestTick?.(initialRemaining);

    targetEndTimeRef.current = Date.now() + initialRemaining * 1000;

    let tenSecondsWarned = initialRemaining <= 10;
    let isFinishedTriggered = false;

    // Solo anunciar "descanso" al entrar inicialmente al descanso
    if (!isResuming) {
      playCueWithFallback("descanso", player, fallback, restController.signal).catch(() => {});
    }

    timerIntervalRef.current = setInterval(async () => {
      if (restController.signal.aborted || isFinishedTriggered) {
        return;
      }

      const currentRemaining = Math.max(
        0,
        Math.ceil((targetEndTimeRef.current! - Date.now()) / 1000),
      );

      setTimerSeconds(currentRemaining);
      onRestTick?.(currentRemaining);

      // Aviso a los 10 s (AC-8-2: no duplicar si el descanso original es <= 10 s)
      if (!tenSecondsWarned && currentRemaining <= 10 && currentRemaining > 0) {
        tenSecondsWarned = true;
        playCueWithFallback("diez-segundos", player, fallback, restController.signal).catch(() => {});
      }

      // Al terminar el descanso (AC-8-2: esperar a que termine el cue antes del siguiente ejercicio)
      if (currentRemaining <= 0) {
        isFinishedTriggered = true;
        clearTimer();
        onRestTick?.(0);

        try {
          await playCueWithFallback("fin-descanso", player, fallback, restController.signal);
        } catch {
          // Ignorar fallo
        }

        if (restController.signal.aborted) {
          return;
        }

        onRestEnd?.();
        dispatch({ type: "timerEnded" });
      }
    }, 250);

    return () => {
      restController.abort();
      if (restAbortRef.current === restController) {
        restAbortRef.current = null;
      }
      clearTimer();
    };
  }, [clearTimer, currentExercise, fallback, onRestEnd, onRestTick, player, state.currentSet, state.exerciseIndex, state.status]);

  // Manejo del estado finished (AC-7-3 y AC-8-2)
  useEffect(() => {
    if (state.status !== "finished") {
      return;
    }
    stopActiveSpeechAndAudio();
    const controller = new AbortController();
    playCueWithFallback("fin-rutina", player, fallback, controller.signal).catch(() => {});
    return () => {
      controller.abort();
    };
  }, [fallback, player, state.status, stopActiveSpeechAndAudio]);

  // Manejo del estado paused (AC-9-2)
  useEffect(() => {
    if (state.status === "paused") {
      clearTimer();
      if (restAbortRef.current) {
        if (targetEndTimeRef.current !== null) {
          const rem = Math.max(0, Math.ceil((targetEndTimeRef.current - Date.now()) / 1000));
          pausedRemainingRef.current = rem;
        }
        restAbortRef.current.abort();
        restAbortRef.current = null;
      } else if (targetEndTimeRef.current !== null) {
        const rem = Math.max(0, Math.ceil((targetEndTimeRef.current - Date.now()) / 1000));
        pausedRemainingRef.current = rem;
      }
      player.pause();
      fallback.pause();
      if (typeof window !== "undefined" && "speechSynthesis" in window && window.speechSynthesis) {
        try {
          window.speechSynthesis.pause();
        } catch {}
      }
    }
  }, [clearTimer, fallback, player, state.status]);

  // Limpieza total al desmontar
  useEffect(() => {
    return () => {
      stopActiveSpeechAndAudio();
      if (preloadAbortRef.current) {
        preloadAbortRef.current.abort();
      }
    };
  }, [stopActiveSpeechAndAudio]);

  // Acciones de control accesibles (AC-9-1 a AC-9-5)
  const next = useCallback(() => {
    stopActiveSpeechAndAudio();
    dispatch({ type: "next" });
  }, [stopActiveSpeechAndAudio]);

  const previous = useCallback(() => {
    stopActiveSpeechAndAudio();
    dispatch({ type: "previous" });
  }, [stopActiveSpeechAndAudio]);

  const pause = useCallback(() => {
    dispatch({ type: "pause" });
  }, []);

  const resume = useCallback(() => {
    dispatch({ type: "resume" });
    if (typeof window !== "undefined" && "speechSynthesis" in window && window.speechSynthesis) {
      try {
        window.speechSynthesis.resume();
      } catch {}
    }
  }, []);

  const repeat = useCallback(() => {
    stopActiveSpeechAndAudio();
    dispatch({ type: "repeat" });
  }, [stopActiveSpeechAndAudio]);

  const exit = useCallback(() => {
    stopActiveSpeechAndAudio();
    dispatch({ type: "exit" });
  }, [stopActiveSpeechAndAudio]);

  const done = useCallback(() => {
    stopActiveSpeechAndAudio();
    dispatch({ type: "done" });
  }, [stopActiveSpeechAndAudio]);

  return {
    state,
    status: state.status,
    exerciseIndex: state.exerciseIndex,
    currentSet: state.currentSet,
    totalSets: state.totalSets,
    currentExercise,
    timerSeconds,
    isLoadingAudio,
    isFirstExercise: state.exerciseIndex === 0,
    isLastExercise: state.exerciseIndex >= exercises.length - 1,
    isPaused: state.status === "paused",
    isFinished: state.status === "finished",
    next,
    previous,
    pause,
    resume,
    repeat,
    exit,
    done,
  };
}
