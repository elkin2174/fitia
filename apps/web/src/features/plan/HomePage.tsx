import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
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
import { WeekLanes } from "./WeekLanes";

export const POLL_INTERVAL_MS = 3000;
export const SLOW_GENERATION_MS = 60_000;

const FAILURE_MESSAGES: Record<string, string> = {
  GENERATION_TIMEOUT: "La generación tardó más de lo esperado.",
  AI_UNAVAILABLE: "El servicio de planes no está disponible ahora.",
  AI_INVALID_OUTPUT: "No pudimos armar un plan válido.",
  STALE: "La generación se interrumpió.",
};
const failureText = (code: string) => FAILURE_MESSAGES[code] ?? "No pudimos armar tu plan.";

const ROTATING = [
  "Revisando tu objetivo y tu nivel…",
  "Ajustando cada sesión a tus minutos disponibles…",
  "Eligiendo ejercicios según tu acceso a máquinas…",
  "Escribiendo una explicación breve para cada ejercicio…",
];

const isBusy = (plan: CurrentPlan | undefined) => Boolean(plan && (plan.status === "generating" || plan.regenerating));

export function HomePage() {
  const me = useMe();
  const queryClient = useQueryClient();
  const plan = useQuery({
    queryKey: planKey,
    queryFn: planApi.current,
    // Sondeo solo mientras se genera; nunca bloquea el resto de la app.
    refetchInterval: (query) => (isBusy(query.state.data) ? POLL_INTERVAL_MS : false),
    staleTime: 0,
  });

  const generate = useMutation({
    mutationFn: planApi.generate,
    onSettled: (_data, error) => {
      if (!error || isApiError(error, "PLAN_UP_TO_DATE")) void queryClient.invalidateQueries({ queryKey: planKey });
    },
  });

  // "none" → se genera automáticamente una sola vez. "failed" NUNCA se reintenta solo.
  const autoStarted = useRef(false);
  useEffect(() => {
    if (plan.data?.status === "none" && !autoStarted.current) {
      autoStarted.current = true;
      generate.mutate();
    }
  }, [plan.data?.status, generate]);

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

        {(data.status === "generating" || (data.status === "none" && !generate.isError)) && (
          <GeneratingPanel slow={slow.reached} onKeepWaiting={slow.reset} onRetry={() => generate.mutate()} retrying={generate.isPending} />
        )}

        {data.status === "none" && generate.isError && (
          <EmptyState
            title="Aún no tienes plan para esta semana"
            action={<Button onClick={() => generate.mutate()} loading={generate.isPending}>Generar mi plan</Button>}
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

function GeneratingPanel({ slow, onKeepWaiting, onRetry, retrying }: { slow: boolean; onKeepWaiting: () => void; onRetry: () => void; retrying: boolean }) {
  const [index, setIndex] = useState(0);
  useEffect(() => {
    const timer = window.setInterval(() => setIndex((i) => (i + 1) % ROTATING.length), 4000);
    return () => window.clearInterval(timer);
  }, []);
  return (
    <section className="rounded-[var(--radius-card)] border-2 border-line bg-surface p-6" aria-labelledby="generating-title">
      <h2 id="generating-title" className="text-2xl font-bold">
        Estamos armando tu plan…
      </h2>
      <p role="status" className="sr-only">Estamos armando tu plan. Te avisaremos cuando esté listo.</p>
      <div className="relative mt-5 h-3 overflow-hidden rounded-full bg-surface-2" aria-hidden="true">
        <div className="animate-runner absolute inset-y-0 w-1/4 rounded-full bg-primary" />
      </div>
      <p className="mt-4 min-h-12 text-muted" aria-hidden="true">
        {ROTATING[index]}
      </p>
      <p className="text-sm text-muted">Puedes seguir usando la app; te mostramos el plan apenas esté listo.</p>
      {slow && (
        <div className="mt-5 flex flex-col gap-3 border-t border-line pt-5" role="status">
          <p className="font-bold">Está tardando más de lo normal.</p>
          <div className="flex flex-wrap gap-2">
            <Button variant="secondary" onClick={onKeepWaiting}>Seguir esperando</Button>
            <Button onClick={onRetry} loading={retrying} loadingText="Reintentando…">Reintentar</Button>
          </div>
        </div>
      )}
    </section>
  );
}

/** Se activa cuando una espera supera `ms`; `reset` vuelve a empezar la cuenta. */
function useSlowFlag(active: boolean, ms: number) {
  const [reached, setReached] = useState(false);
  const [round, setRound] = useState(0);
  useEffect(() => {
    setReached(false);
    if (!active) return;
    const timer = window.setTimeout(() => setReached(true), ms);
    return () => window.clearTimeout(timer);
  }, [active, ms, round]);
  return { reached: active && reached, reset: () => setRound((r) => r + 1) };
}
