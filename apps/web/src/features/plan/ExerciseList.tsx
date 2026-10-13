import type { PlanExercise } from "../../shared/api/types";
import {
  formatPrescriptionAriaLabel,
  formatPrescriptionSummary,
} from "../../shared/lib/prescription";

export interface ExerciseListProps {
  exercises: PlanExercise[];
  onSelectExercise: (exercise: PlanExercise) => void;
}

export function ExerciseList({ exercises, onSelectExercise }: ExerciseListProps) {
  if (!exercises.length) return null;

  return (
    <ol className="flex flex-col gap-3" aria-label="Lista de ejercicios de la rutina">
      {exercises.map((exercise) => {
        const prescriptionText = formatPrescriptionSummary(exercise);
        const ariaLabel = `${formatPrescriptionAriaLabel(
          exercise,
          exercise.name
        )}. Toca para ver la técnica.`;

        return (
          <li key={exercise.id}>
            <button
              type="button"
              onClick={() => onSelectExercise(exercise)}
              aria-label={ariaLabel}
              className="group flex w-full min-h-[44px] items-center justify-between gap-3 rounded-[var(--radius-card)] border-2 border-line bg-surface p-4 text-left transition-colors hover:border-primary/50 hover:bg-surface-2 focus-visible:outline-2 focus-visible:outline-focus cursor-pointer"
            >
              <div className="flex items-center gap-3 min-w-0">
                <span
                  className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-surface-2 text-sm font-bold text-muted group-hover:bg-primary group-hover:text-on-primary transition-colors"
                  aria-hidden="true"
                >
                  {exercise.position}
                </span>
                <div className="min-w-0">
                  <h3 className="font-bold text-base text-ink truncate">
                    {exercise.name}
                  </h3>
                  <p className="text-sm text-muted">
                    {prescriptionText}
                  </p>
                </div>
              </div>

              <div className="flex shrink-0 items-center gap-1 text-muted group-hover:text-primary transition-colors">
                <span className="text-xs font-medium hidden xs:inline">Ver técnica</span>
                <svg
                  className="h-5 w-5"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                  aria-hidden="true"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M9 5l7 7-7 7"
                  />
                </svg>
              </div>
            </button>
          </li>
        );
      })}
    </ol>
  );
}
