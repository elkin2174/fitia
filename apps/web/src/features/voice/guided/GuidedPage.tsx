import { useQuery } from "@tanstack/react-query";
import { useCallback } from "react";
import { Navigate, useNavigate } from "react-router";
import { Page } from "../../../app/AppLayout";
import type { PlanExercise } from "../../../shared/api/types";
import { formatSets, formatWork } from "../../../shared/lib/prescription";
import { Button } from "../../../shared/ui/Button";
import { ErrorState, PageSkeleton } from "../../../shared/ui/Feedback";
import { planApi, todayKey } from "../../plan/api";
import { useGuidedSession } from "./useGuidedSession";
import { useWakeLock } from "./useWakeLock";

interface GuidedSessionContentProps {
  exercises: PlanExercise[];
}

function GuidedSessionContent({ exercises }: GuidedSessionContentProps) {
  const navigate = useNavigate();

  const {
    status,
    exerciseIndex,
    currentSet,
    totalSets,
    currentExercise,
    timerSeconds,
    isLoadingAudio,
    isFirstExercise,
    isLastExercise,
    isPaused,
    isFinished,
    next,
    previous,
    pause,
    resume,
    repeat,
    exit,
    done,
  } = useGuidedSession({
    exercises,
    autoStart: true,
  });

  // AC-10-2, AC-10-3, AC-10-4: Pantalla activa mediante Wake Lock
  const { isActive: isWakeLockActive } = useWakeLock(!isFinished);

  const handleExit = useCallback(() => {
    exit();
    navigate("/hoy");
  }, [exit, navigate]);

  if (!currentExercise && !isFinished) {
    return <Navigate to="/hoy" replace />;
  }

  return (
    <Page>
      {/* Barra superior de navegación y control */}
      <div className="mb-4 flex items-center justify-between border-b border-line pb-3">
        <Button
          variant="ghost"
          onClick={handleExit}
          className="text-muted hover:text-ink min-h-[44px]"
          aria-label="Salir del modo guiado"
          icon={
            <svg
              className="h-5 w-5 shrink-0"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
              aria-hidden="true"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
          }
        >
          Salir
        </Button>

        <span className="text-xs font-bold uppercase tracking-wider text-muted">
          Modo guiado por voz
        </span>
      </div>

      {/* Pantalla de Fin de Rutina (AC-7-3) */}
      {isFinished ? (
        <div
          className="flex flex-col items-center justify-center gap-6 rounded-[var(--radius-card)] border-2 border-line bg-surface p-8 text-center"
          role="status"
          aria-live="polite"
        >
          <div className="grid h-16 w-16 place-items-center rounded-full bg-surface-2 text-primary">
            <svg
              className="h-8 w-8"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
              aria-hidden="true"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
            </svg>
          </div>

          <div>
            <h1 className="text-2xl font-extrabold text-ink sm:text-3xl">
              ¡Rutina completada!
            </h1>
            <p className="mt-2 text-lg text-muted">
              Terminaste la rutina de hoy. ¡Buen trabajo!
            </p>
          </div>

          <Button
            variant="primary"
            onClick={handleExit}
            className="w-full sm:w-auto min-h-[44px]"
            aria-label="Volver a la rutina de hoy"
          >
            Volver a la rutina de hoy
          </Button>
        </div>
      ) : currentExercise ? (
        <div className="flex flex-col gap-5">
          {/* Tarjeta principal del ejercicio */}
          <section
            className="flex flex-col gap-4 rounded-[var(--radius-card)] border-2 border-line bg-surface p-6"
            aria-label={`Ejercicio actual: ${currentExercise.name}`}
          >
            {/* Encabezado de progreso */}
            <div className="flex items-center justify-between text-xs font-bold uppercase tracking-wider text-muted">
              <span>
                Ejercicio {exerciseIndex + 1} de {exercises.length}
              </span>
              <span className="rounded-full bg-surface-2 px-2.5 py-0.5 text-ink">
                Serie {currentSet} de {totalSets}
              </span>
            </div>

            {/* Nombre y prescripción del ejercicio */}
            <div>
              <h1 className="text-2xl font-extrabold text-ink sm:text-3xl">
                {currentExercise.name}
              </h1>
              <p className="mt-1 text-sm font-semibold text-muted">
                {formatSets(currentExercise.sets)} · {formatWork(currentExercise.reps, currentExercise.work_seconds)} · Descanso {currentExercise.rest_seconds} s
              </p>
            </div>

            {/* Estado dinámico de la sesión */}
            <div className="rounded-[var(--radius-control)] border border-line bg-surface-2 p-5 text-center">
              {status === "announcing" && (
                <div className="flex flex-col items-center gap-3" role="status" aria-live="polite">
                  {isLoadingAudio ? (
                    <>
                      <div className="h-6 w-6 animate-spin rounded-full border-2 border-primary border-t-transparent" />
                      <p className="text-base font-semibold text-ink">Preparando audio…</p>
                    </>
                  ) : (
                    <>
                      <div className="grid h-10 w-10 place-items-center rounded-full bg-surface text-primary">
                        <svg
                          className="h-5 w-5 animate-pulse"
                          fill="none"
                          stroke="currentColor"
                          viewBox="0 0 24 24"
                          aria-hidden="true"
                        >
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth={2}
                            d="M15.536 8.464a5 5 0 010 7.072m2.828-9.9a9 9 0 010 12.728M5.586 15H4a1 1 0 01-1-1v-4a1 1 0 011-1h1.586l4.707-4.707C10.923 3.663 12 4.109 12 5v14c0 .891-1.077 1.337-1.707.707L5.586 15z"
                          />
                        </svg>
                      </div>
                      <p className="text-base font-semibold text-ink">
                        {currentSet === 1 ? "Explicando técnica del ejercicio…" : `Preparando serie ${currentSet}…`}
                      </p>
                    </>
                  )}
                </div>
              )}

              {status === "working" && (
                <div className="flex flex-col items-center gap-4" role="status" aria-live="polite">
                  <span className="text-xs font-bold uppercase tracking-wider text-muted">
                    ¡A entrenar!
                  </span>

                  {currentExercise.work_seconds ? (
                    <div className="text-5xl font-black text-primary">
                      {timerSeconds !== null ? `${timerSeconds} s` : `${currentExercise.work_seconds} s`}
                    </div>
                  ) : (
                    <div className="text-4xl font-black text-ink">
                      {currentExercise.reps} {currentExercise.reps === 1 ? "repetición" : "repeticiones"}
                    </div>
                  )}

                  <Button
                    variant="primary"
                    onClick={done}
                    className="w-full sm:w-auto min-h-[44px]"
                    aria-label="Terminar serie actual"
                  >
                    Terminar serie
                  </Button>
                </div>
              )}

              {status === "resting" && (
                <div className="flex flex-col items-center gap-4" role="status" aria-live="polite">
                  <span className="text-xs font-bold uppercase tracking-wider text-muted">
                    Descanso
                  </span>

                  <div className="text-5xl font-black text-ink">
                    {timerSeconds !== null ? `${timerSeconds} s` : `${currentExercise.rest_seconds} s`}
                  </div>

                  <p className="text-xs text-muted">
                    {currentSet < totalSets
                      ? `Siguiente: Serie ${currentSet + 1} de ${totalSets}`
                      : exerciseIndex < exercises.length - 1
                      ? `Siguiente: ${exercises[exerciseIndex + 1]?.name}`
                      : "Último descanso de la rutina"}
                  </p>

                  <Button
                    variant="secondary"
                    onClick={done}
                    className="w-full sm:w-auto min-h-[44px]"
                    aria-label="Saltar descanso"
                  >
                    Saltar descanso
                  </Button>
                </div>
              )}

              {status === "paused" && (
                <div className="flex flex-col items-center gap-3" role="status" aria-live="polite">
                  <span className="text-xs font-bold uppercase tracking-wider text-primary">
                    Pausado
                  </span>
                  <p className="text-base font-semibold text-ink">
                    Entrenamiento en pausa
                  </p>
                  <p className="text-xs text-muted">
                    Pulsa «Continuar» para retomar exactamente donde quedaste.
                  </p>
                </div>
              )}
            </div>
          </section>

          {/* Controles de navegación y reproducción (AC-9-1 a AC-9-5) */}
          <section
            className="flex flex-wrap items-center justify-between gap-2 rounded-[var(--radius-card)] border-2 border-line bg-surface p-3"
            aria-label="Controles del modo guiado"
          >
            <Button
              variant="secondary"
              onClick={previous}
              disabled={isFirstExercise}
              className="flex-1 min-h-[44px]"
              aria-label="Ejercicio anterior"
            >
              Anterior
            </Button>

            {isPaused ? (
              <Button
                variant="primary"
                onClick={resume}
                className="flex-1 min-h-[44px]"
                aria-label="Continuar entrenamiento"
                icon={
                  <svg className="h-4 w-4 shrink-0" fill="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                    <polygon points="5 3 19 12 5 21 5 3" />
                  </svg>
                }
              >
                Continuar
              </Button>
            ) : (
              <Button
                variant="secondary"
                onClick={pause}
                className="flex-1 min-h-[44px]"
                aria-label="Pausar entrenamiento"
                icon={
                  <svg className="h-4 w-4 shrink-0" fill="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                    <rect x="6" y="4" width="4" height="16" />
                    <rect x="14" y="4" width="4" height="16" />
                  </svg>
                }
              >
                Pausar
              </Button>
            )}

            <Button
              variant="secondary"
              onClick={repeat}
              className="flex-1 min-h-[44px]"
              aria-label="Repetir explicación del ejercicio actual"
              icon={
                <svg className="h-4 w-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                </svg>
              }
            >
              Repetir
            </Button>

            <Button
              variant="secondary"
              onClick={next}
              disabled={isLastExercise}
              className="flex-1 min-h-[44px]"
              aria-label="Siguiente ejercicio"
            >
              Siguiente
            </Button>
          </section>

          {/* Indicador de pantalla activa (AC-10-2) */}
          {isWakeLockActive && (
            <p className="text-center text-xs text-muted" aria-live="off">
              Pantalla activa durante el entrenamiento
            </p>
          )}
        </div>
      ) : null}
    </Page>
  );
}

export function GuidedPage() {
  const todayQuery = useQuery({
    queryKey: todayKey,
    queryFn: planApi.today,
    staleTime: 0,
  });

  const data = todayQuery.data;

  // AC-10-1: Redirigir a /hoy si no es día de entrenamiento o no hay plan listo
  const isTrainingDay = Boolean(
    data &&
      data.plan_status === "ready" &&
      data.day?.status === "training" &&
      !data.is_weekend &&
      data.day.exercises.length > 0,
  );

  if (todayQuery.isPending) {
    return (
      <Page>
        <PageSkeleton label="Cargando tu sesión guiada…" rows={5} />
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

  // Redirección si no es día de entrenamiento válido (AC-10-1)
  if (!isTrainingDay || !data?.day?.exercises) {
    return <Navigate to="/hoy" replace />;
  }

  return <GuidedSessionContent exercises={data.day.exercises} />;
}
