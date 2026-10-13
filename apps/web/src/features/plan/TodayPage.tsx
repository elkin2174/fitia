import { useQuery } from "@tanstack/react-query";
import { useCallback } from "react";
import { useSearchParams } from "react-router";
import { Page } from "../../app/AppLayout";
import { formatDayLong, formatDayMonth } from "../../shared/lib/dates";
import { Banner } from "../../shared/ui/Banner";
import { Button, ButtonLink } from "../../shared/ui/Button";
import { EmptyState, ErrorState, PageSkeleton } from "../../shared/ui/Feedback";
import { planApi, todayKey } from "./api";
import { DayRoutine } from "./DayRoutine";
import { ExerciseGuideSheet } from "./ExerciseGuideSheet";
import { GeneratingPanel } from "./GeneratingPanel";
import {
  POLL_INTERVAL_MS,
  SLOW_GENERATION_MS,
  failureText,
  usePlanGeneration,
  useSlowFlag,
} from "./usePlanGeneration";

export function TodayPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const { generate } = usePlanGeneration();

  const todayQuery = useQuery({
    queryKey: todayKey,
    queryFn: planApi.today,
    refetchInterval: (query) => {
      const data = query.state.data;
      return data?.plan_status === "generating" || data?.regenerating
        ? POLL_INTERVAL_MS
        : false;
    },
    staleTime: 0,
  });

  const isBusy: boolean = Boolean(
    todayQuery.data &&
      (todayQuery.data.plan_status === "generating" ||
        todayQuery.data.regenerating)
  );
  const slow = useSlowFlag(isBusy, SLOW_GENERATION_MS);

  const handleSelectExercise = useCallback((exercise: { id: string }) => {
    setSearchParams({ ejercicio: exercise.id }, { replace: true });
  }, [setSearchParams]);

  const handleCloseGuide = useCallback(() => {
    setSearchParams({}, { replace: true });
  }, [setSearchParams]);

  if (todayQuery.isPending) {
    return (
      <Page>
        <PageSkeleton label="Cargando tu rutina de hoy…" rows={5} />
      </Page>
    );
  }

  if (todayQuery.isError) {
    return (
      <Page>
        <ErrorState
          message={todayQuery.error.message}
          onRetry={() => todayQuery.refetch()}
        />
      </Page>
    );
  }

  const data = todayQuery.data;
  const ejercicioId = searchParams.get("ejercicio");
  const selectedExercise =
    data.day?.exercises.find((e) => e.id === ejercicioId) ?? null;

  return (
    <Page>
      <header className="mb-6">
        <p className="text-sm font-bold text-primary-text uppercase tracking-wider">
          Hoy · {formatDayLong(data.date)}
        </p>
        <h1 className="mt-1 text-3xl font-extrabold text-ink">
          {data.is_weekend
            ? "Fin de semana de descanso"
            : data.day?.status === "training"
            ? "Tu rutina de hoy"
            : "Día de descanso"}
        </h1>
      </header>

      <div className="flex flex-col gap-6">
        {/* Panel de generación en progreso */}
        {data.plan_status === "generating" && (
          <GeneratingPanel
            slow={slow.reached}
            onKeepWaiting={slow.reset}
            onRetry={() => generate.mutate()}
            retrying={generate.isPending}
          />
        )}

        {/* Estado fallido */}
        {data.plan_status === "failed" && data.failure && (
          <Banner
            tone="danger"
            title={failureText(data.failure.code)}
            live="assertive"
            actions={
              <Button
                onClick={() => generate.mutate()}
                loading={generate.isPending}
                loadingText="Reintentando…"
              >
                Reintentar
              </Button>
            }
          >
            No pudimos generar tu plan. Intenta nuevamente o vuelve en unos minutos.
          </Banner>
        )}

        {/* Estado sin plan (AC-10-3) */}
        {data.plan_status === "none" && (
          <EmptyState
            title="Aún no tienes plan para esta semana"
            action={
              <Button
                onClick={() => generate.mutate()}
                loading={generate.isPending}
                loadingText="Generando…"
              >
                Generar mi plan
              </Button>
            }
          >
            {data.next_training_day ? (
              <p>
                Tu próximo día sugerido es el{" "}
                <span className="font-semibold text-ink">
                  {formatDayLong(data.next_training_day.date)}
                </span>
                . Genera tu plan para activar tu rutina.
              </p>
            ) : (
              "Tus respuestas del diagnóstico ya están listas para armar tu plan."
            )}
          </EmptyState>
        )}

        {/* Plan listo: día de entrenamiento (AC-10-1) */}
        {data.plan_status === "ready" && data.day?.status === "training" && (
          <DayRoutine
            day={data.day}
            onSelectExercise={handleSelectExercise}
          />
        )}

        {/* Plan listo: día de descanso o fin de semana (AC-10-2) */}
        {data.plan_status === "ready" &&
          (data.day?.status === "rest" || data.is_weekend) && (
            <div className="flex flex-col gap-4">
              <div className="rounded-[var(--radius-card)] border-2 border-line bg-surface p-6">
                <div className="flex items-center gap-3">
                  <div className="grid h-10 w-10 shrink-0 place-items-center rounded-full bg-surface-2 text-primary">
                    <svg
                      className="h-6 w-6"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                      aria-hidden="true"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z"
                      />
                    </svg>
                  </div>
                  <div>
                    <h2 className="text-lg font-bold text-ink">
                      {data.is_weekend
                        ? "Recupérate este fin de semana"
                        : "Hoy no tienes entrenamiento programado"}
                    </h2>
                    <p className="text-sm text-muted">
                      El descanso es fundamental para consolidar el progreso y evitar lesiones.
                    </p>
                  </div>
                </div>
              </div>

              {data.next_training_day && (
                <section
                  className="rounded-[var(--radius-card)] border-2 border-line bg-surface p-6"
                  aria-labelledby="next-training-title"
                >
                  <p
                    id="next-training-title"
                    className="text-xs font-bold text-muted uppercase tracking-wider"
                  >
                    Próxima sesión
                  </p>
                  <p className="mt-1 text-xl font-bold text-ink">
                    {formatDayLong(data.next_training_day.date)}
                  </p>
                  {data.next_training_day.title && (
                    <p className="text-sm text-muted">
                      {data.next_training_day.title}
                    </p>
                  )}

                  <div className="mt-4">
                    {data.next_training_day.planned ? (
                      <ButtonLink
                        to={`/plan/dia/${data.next_training_day.date}`}
                        variant="secondary"
                      >
                        Ver rutina del {formatDayMonth(data.next_training_day.date)}
                      </ButtonLink>
                    ) : (
                      <Button
                        onClick={() => generate.mutate()}
                        loading={generate.isPending}
                        loadingText="Generando…"
                      >
                        Generar mi plan
                      </Button>
                    )}
                  </div>
                </section>
              )}
            </div>
          )}
      </div>

      <ExerciseGuideSheet
        exercise={selectedExercise}
        onClose={handleCloseGuide}
      />
    </Page>
  );
}
