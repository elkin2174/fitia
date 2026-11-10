import { useCallback, useSyncExternalStore } from "react";
import { globalAudioPlayer, type AudioPlayer } from "./AudioPlayer";
import type { PlaybackRate } from "./playbackRate";

export function useExerciseAudio(
  exerciseId: string | null,
  player: AudioPlayer = globalAudioPlayer,
) {
  const snapshot = useSyncExternalStore(
    player.subscribe,
    player.getSnapshot,
    player.getSnapshot,
  );

  const isCurrent = Boolean(exerciseId && snapshot.exerciseId === exerciseId);
  const state = isCurrent ? snapshot.state : "idle";
  const error = isCurrent ? snapshot.error : null;

  const isLoading = state === "loading";
  const isPlaying = state === "playing";
  const isPaused = state === "paused";
  const hasAudio = isPlaying || isPaused;

  const play = useCallback(async () => {
    if (!exerciseId || isLoading) return;
    await player.play(exerciseId);
  }, [exerciseId, isLoading, player]);

  const pause = useCallback(() => {
    if (isCurrent) {
      player.pause();
    }
  }, [isCurrent, player]);

  const resume = useCallback(async () => {
    if (isCurrent) {
      await player.resume();
    }
  }, [isCurrent, player]);

  const restart = useCallback(async () => {
    if (isCurrent) {
      await player.restart();
    }
  }, [isCurrent, player]);

  const stop = useCallback(() => {
    player.stop();
  }, [player]);

  const setRate = useCallback(
    (rate: PlaybackRate) => {
      player.setRate(rate);
    },
    [player],
  );

  return {
    state,
    isLoading,
    isPlaying,
    isPaused,
    hasAudio,
    rate: snapshot.rate,
    error,
    play,
    pause,
    resume,
    restart,
    stop,
    setRate,
  };
}
