import { useQuery } from "@tanstack/react-query";
import { useEffect, useRef } from "react";
import { useLocation } from "react-router";
import { Page } from "../../app/AppLayout";
import { isApiError } from "../../shared/api/client";
import type { CurrentPlan } from "../../shared/api/types";
import { formatDayLong, formatDayMonth, todayInBogota } from "../../shared/lib/dates";
import { describeWait, describeWaitUntilDay } from "../../shared/lib/retryAfter";
import { useMe } from "../../shared/session/session";
import { Banner } from "../../shared/ui/Banner";
import { Button } from "../../shared/ui/Button";
import { EmptyState, ErrorState, PageSkeleton } from "../../shared/ui/Feedback";
import { planApi, planKey } from "./api";
import { GeneratingPanel } from "./GeneratingPanel";
import {
  POLL_INTERVAL_MS,
  SLOW_GENERATION_MS,
  failureText,
  usePlanGeneration,
  useSlowFlag,
} from "./usePlanGeneration";
import { WeekLanes } from "./WeekLanes";

export { POLL_INTERVAL_MS, SLOW_GENERATION_MS };

const isBusy = (plan: CurrentPlan | undefined) => Boolean(plan && (plan.status === "generating" || plan.regenerating));

export function HomePage() {
  const me = useMe();
  const location = useLocation();
  const { generate } = usePlanGeneration();
  const plan = useQuery({
    queryKey: planKey,
    queryFn: planApi.current,
    // Sondeo solo mientras se genera; nunca bloquea el resto de la app.
    refetchInterval: (query) => (isBusy(query.state.data) ? POLL_INTERVAL_MS : false),
    staleTime: 0,
  });

  // Decisión 8: la generación automática se mantiene SOLO cuando el usuario llega justo después del diagnóstico.
  // En cualquier otro caso (none en semana nueva), muestra EmptyState con "Generar mi plan".
  const autoStarted = useRef(false);
  const fromDiagnostic = Boolean(
    (location.state as { fromDiagnostic?: boolean } | null)?.fromDiagnostic
  );

  useEffect(() => {
    if (plan.data?.status === "none" && !autoStarted.current && fromDiagnostic) {
      autoStarted.current = true;
      generate.mutate();
    }
  }, [plan.data?.status, fromDiagnostic, generate]);

  const busy = isBusy(plan.data);
  const slow = useSlowFlag(busy, SLOW_GENERATION_MS);

  if (plan.isPending) {
    return (
      <Page>
        <PageSkeleton label="Cargando tu plan…" rows={5} />
      </Page>
    );
  }
  if (plan.isError) {
    return (
      <Page>
        <ErrorState message={plan.error.message} onRetry={() => plan.refetch()} />
      </Page>
    );
  }

  const data = plan.data;
  const today = todayInBogota();
  const nextWeek = data.week_start > today;
  const hasReady = data.status === "ready";
  const trainingDays = data.days.filter((d) => d.status === "training");

  return (
    <Page>
      <p className="font-bold text-primary-text">Hola, {me.data?.nickname}</p>
      <h1 className="mt-1 text-3xl font-extrabold">
        {nextWeek ? `Tu plan para la semana del ${formatDayMonth(data.week_start)}` : "Tu semana"}
      </h1>
      <p className="mt-1 text-muted">
        {nextWeek ? "Este fin de semana preparamos la siguiente." : `Hoy es ${formatDayLong(today)}.`}
      </p>

      <div className="mt-6 flex flex-col gap-4">
        <GenerateFeedback error={generate.error} />

        {(data.status === "generating" || (data.status === "none" && generate.isPending)) && (
          <GeneratingPanel
            slow={slow.reached}
            onKeepWaiting={slow.reset}
            onRetry={() => generate.mutate()}
            retrying={generate.isPending}
          />
        )}

        {data.status === "none" && !generate.isPending && (
          <EmptyState
            title="Aún no tienes plan para esta semana"
            action={<Button onClick={() => generate.mutate()} loading={generate.isPending} loadingText="Generando…">Generar mi plan</Button>}
          >
            Tus respuestas del diagnóstico ya están guardadas.
          </EmptyState>
        )}

        {data.status === "failed" && data.failure && (
          <Banner
            tone="danger"
            title={failureText(data.failure.code)}
            live="assertive"
            actions={<Button onClick={() => generate.mutate()} loading={generate.isPending} loadingText="Reintentando…">Reintentar</Button>}
          >
            Tus respuestas están guardadas. Intenta de nuevo; si sigue fallando, vuelve en unos minutos.
          </Banner>
        )}

        {hasReady && data.regenerating && (
          <Banner tone="info" title="Estamos actualizando tu plan…">
            Mientras tanto, este sigue siendo tu plan de la semana.
            {slow.reached && (
              <div className="mt-2 flex flex-wrap gap-2">
                <Button variant="secondary" onClick={slow.reset}>Seguir esperando</Button>
                <Button variant="ghost" onClick={() => generate.mutate()}>Reintentar</Button>
              </div>
            )}
          </Banner>
        )}

        {hasReady && data.failure && !data.regenerating && (
          <Banner
            tone="warn"
            title="No pudimos actualizar tu plan."
            actions={data.can_regenerate && <Button variant="secondary" onClick={() => generate.mutate()} loading={generate.isPending}>Reintentar</Button>}
          >
            {failureText(data.failure.code)} Tu plan anterior sigue vigente.
          </Banner>
        )}

        {hasReady && data.outdated && !data.regenerating && !data.failure && (
          <Banner
            tone="info"
            title="Cambiaste tu diagnóstico. ¿Quieres actualizar tu plan?"
            actions={
              data.can_regenerate && (
                <Button onClick={() => generate.mutate()} loading={generate.isPending} loadingText="Enviando…">
                  Actualizar mi plan
                </Button>
              )
            }
          >
            {data.can_regenerate
              ? "Tu plan actual no cambia hasta que lo actualices."
              : "Ya usaste las actualizaciones de esta semana. El lunes podrás generar un plan con tus nuevas respuestas."}
          </Banner>
        )}

        {hasReady && trainingDays.length === 0 && (
          <EmptyState title="No quedan días de entrenamiento esta semana">
            Los días que elegiste ya pasaron. El próximo lunes armamos tu plan de la nueva semana.
          </EmptyState>
        )}

        {hasReady && <WeekLanes days={data.days} today={today} />}
      </div>
    </Page>
  );
}

function GenerateFeedback({ error }: { error: Error | null }) {
  if (!error || isApiError(error, "PLAN_UP_TO_DATE")) return null;
  if (isApiError(error, "REGENERATION_LIMIT")) {
    return (
      <Banner tone="warn" live="assertive">
        Ya usaste tus actualizaciones de esta semana; podrás generar uno nuevo{" "}
        {error.retryAfter ? describeWaitUntilDay(error.retryAfter) : "el lunes"}.
      </Banner>
    );
  }
  if (isApiError(error, "RATE_LIMITED")) {
    return (
      <Banner tone="warn" live="assertive">
        Hiciste varios intentos seguidos. Intenta de nuevo {describeWait(error.retryAfter ?? 60)}.
      </Banner>
    );
  }
  return (
    <Banner tone="danger" live="assertive">
      {error.message}
    </Banner>
  );
}

