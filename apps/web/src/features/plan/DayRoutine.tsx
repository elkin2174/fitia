import type { PlanDayDetail, PlanExercise } from "../../shared/api/types";
import { ExerciseList } from "./ExerciseList";

export interface DayRoutineProps {
  day: PlanDayDetail;
  onSelectExercise: (exercise: PlanExercise) => void;
}

export function DayRoutine({ day, onSelectExercise }: DayRoutineProps) {
  const isTraining = day.status === "training";

  return (
    <section className="flex flex-col gap-4" aria-label="Rutina del día">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-line pb-3">
        <div>
          <h2 className="text-xl font-bold text-ink">
            {day.title || (isTraining ? "Ejercicios de la sesión" : "Sin rutina programada")}
          </h2>
          <p className="text-sm text-muted">
            {isTraining
              ? `${day.exercises.length} ${day.exercises.length === 1 ? "ejercicio" : "ejercicios"}`
              : "Sin rutina para este día"}
          </p>
        </div>

        {isTraining && day.estimated_minutes && (
          <span className="inline-flex items-center gap-1.5 rounded-full bg-surface-2 px-3 py-1 text-sm font-semibold text-muted">
            <svg
              className="h-4 w-4"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
              aria-hidden="true"
            >
              <circle cx="12" cy="12" r="10" strokeWidth="2" />
              <polyline points="12 6 12 12 16 14" strokeWidth="2" strokeLinecap="round" />
            </svg>
            {day.estimated_minutes} min
          </span>
        )}
      </div>

      {isTraining ? (
        <ExerciseList exercises={day.exercises} onSelectExercise={onSelectExercise} />
      ) : (
        <div className="rounded-[var(--radius-card)] border-2 border-line bg-surface p-6 text-center text-muted">
          Este día no tiene ejercicios programados. Aprovecha para descansar y recuperarte.
        </div>
      )}
    </section>
  );
}
