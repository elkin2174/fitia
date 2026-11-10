import { useEffect } from "react";
import type { PlanExercise } from "../../shared/api/types";
import { Banner } from "../../shared/ui/Banner";
import { BottomSheet } from "../../shared/ui/BottomSheet";
import { ListenButton } from "../voice/ListenButton";
import { PlaybackControls } from "../voice/PlaybackControls";
import { useExerciseAudio } from "../voice/useExerciseAudio";

export interface ExerciseGuideSheetProps {
  exercise: PlanExercise | null;
  onClose: () => void;
}

export function ExerciseGuideSheet({ exercise, onClose }: ExerciseGuideSheetProps) {
  const {
    isLoading,
    isPlaying,
    isPaused,
    hasAudio,
    rate,
    error,
    play,
    pause,
    resume,
    restart,
    stop,
    setRate,
  } = useExerciseAudio(exercise?.id ?? null);

  // AC-3-4: si se cierra la explicación o se cambia de ejercicio, el audio se detiene
  useEffect(() => {
    return () => {
      stop();
    };
  }, [exercise?.id, stop]);

  const handleClose = () => {
    stop();
    onClose();
  };

  if (!exercise) return null;

  return (
    <BottomSheet
      open={Boolean(exercise)}
      title={exercise.name}
      onClose={handleClose}
      closeLabel="Cerrar explicación"
    >
      <div className="flex flex-col gap-5">
        {/* Controles de audio de la explicación (HU 3, HU 4, HU 5) */}
        <div className="flex flex-col gap-3 border-b border-line pb-4" aria-label="Audio de la explicación">
          <div className="flex items-center justify-between gap-3">
            <ListenButton
              onListen={play}
              isLoading={isLoading}
              isPlaying={isPlaying}
            />
          </div>

          <PlaybackControls
            hasAudio={hasAudio}
            isPlaying={isPlaying}
            isPaused={isPaused}
            isLoading={isLoading}
            rate={rate}
            error={error}
            onPlay={play}
            onPause={pause}
            onResume={resume}
            onRestart={restart}
            onRateChange={setRate}
            onRetry={play}
          />
        </div>

        <div>
          <h3 className="sr-only">Instrucciones paso a paso</h3>
          <ol className="flex flex-col gap-3 list-decimal list-inside text-base">
            {exercise.guide.steps.map((step, idx) => (
              <li key={idx} className="leading-relaxed pl-1">
                <span className="font-medium text-ink">{step}</span>
              </li>
            ))}
          </ol>
        </div>

        <Banner tone="info" title="Aviso orientativo">
          {exercise.guide.disclaimer}
        </Banner>
      </div>
    </BottomSheet>
  );
}
