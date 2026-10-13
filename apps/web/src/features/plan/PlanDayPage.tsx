import { useQuery } from "@tanstack/react-query";
import { useCallback } from "react";
import { Link, useParams, useSearchParams } from "react-router";
import { Page } from "../../app/AppLayout";
import { formatDayLong } from "../../shared/lib/dates";
import { ErrorState, PageSkeleton } from "../../shared/ui/Feedback";
import { dayKey, planApi } from "./api";
import { DayRoutine } from "./DayRoutine";
import { ExerciseGuideSheet } from "./ExerciseGuideSheet";

export function PlanDayPage() {
  const { fecha } = useParams<{ fecha: string }>();
  const [searchParams, setSearchParams] = useSearchParams();

  const dayQuery = useQuery({
    queryKey: dayKey(fecha ?? ""),
    queryFn: () => planApi.day(fecha ?? ""),
    enabled: Boolean(fecha),
    staleTime: 60_000,
  });

  const handleSelectExercise = useCallback((exercise: { id: string }) => {
    setSearchParams({ ejercicio: exercise.id }, { replace: true });
  }, [setSearchParams]);

  const handleCloseGuide = useCallback(() => {
    setSearchParams({}, { replace: true });
  }, [setSearchParams]);

  if (dayQuery.isPending) {
    return (
      <Page>
        <PageSkeleton label="Cargando rutina del día…" rows={5} />
      </Page>
    );
  }

  if (dayQuery.isError) {
    return (
      <Page>
        <div className="mb-4">
          <Link
            to="/inicio"
            className="inline-flex min-h-[44px] items-center text-sm font-bold text-muted hover:text-ink transition-colors cursor-pointer focus-visible:outline-2 focus-visible:outline-focus rounded-sm"
          >
            ← Volver a la semana
          </Link>
        </div>
        <ErrorState
          message={dayQuery.error.message}
          onRetry={() => dayQuery.refetch()}
        />
      </Page>
    );
  }

  const data = dayQuery.data;
  const ejercicioId = searchParams.get("ejercicio");
  const selectedExercise =
    data.exercises.find((e) => e.id === ejercicioId) ?? null;

  return (
    <Page>
      <div className="mb-4">
        <Link
          to="/inicio"
          className="inline-flex min-h-[44px] items-center text-sm font-bold text-muted hover:text-ink transition-colors cursor-pointer focus-visible:outline-2 focus-visible:outline-focus rounded-sm"
        >
          ← Volver a la semana
        </Link>
      </div>

      <header className="mb-6">
        <p className="text-sm font-bold text-primary-text uppercase tracking-wider">
          {formatDayLong(data.date)}
        </p>
        <h1 className="mt-1 text-3xl font-extrabold text-ink">
          {data.status === "training" ? "Rutina del día" : "Día de descanso"}
        </h1>
      </header>

      <DayRoutine
        day={data}
        onSelectExercise={handleSelectExercise}
      />

      <ExerciseGuideSheet
        exercise={selectedExercise}
        onClose={handleCloseGuide}
      />
    </Page>
  );
}
