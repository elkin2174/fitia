import type { PlanExercise } from "../../shared/api/types";
import { Banner } from "../../shared/ui/Banner";
import { BottomSheet } from "../../shared/ui/BottomSheet";

export interface ExerciseGuideSheetProps {
  exercise: PlanExercise | null;
  onClose: () => void;
}

export function ExerciseGuideSheet({ exercise, onClose }: ExerciseGuideSheetProps) {
  if (!exercise) return null;

  return (
    <BottomSheet
      open={Boolean(exercise)}
      title={exercise.name}
      onClose={onClose}
      closeLabel="Cerrar explicación"
    >
      <div className="flex flex-col gap-5">
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
