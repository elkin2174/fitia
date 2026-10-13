import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router";
import { Page } from "../../app/AppLayout";
import { formatDateFromTimestamp, formatShortFromTimestamp } from "../../shared/lib/dates";
import { ButtonLink } from "../../shared/ui/Button";
import { Card, EmptyState, ErrorState, PageSkeleton } from "../../shared/ui/Feedback";
import { measurementsKey, profileApi } from "./api";
import type { PhysicalMeasurement } from "./types";

export function HistoryPage() {
  const history = useQuery({ queryKey: measurementsKey, queryFn: profileApi.measurements });

  return (
    <Page>
      <Link to="/perfil" className="inline-flex min-h-11 items-center font-bold text-primary-text">
        ‹ Volver al perfil
      </Link>
      <h1 className="mt-2 text-3xl font-extrabold">Historial de peso y estatura</h1>

      <div className="mt-6">
        {history.isPending && <PageSkeleton label="Cargando tu historial…" rows={3} />}
        {history.isError && <ErrorState message={history.error.message} onRetry={() => history.refetch()} />}
        {history.isSuccess && history.data.history.length === 0 && (
          <EmptyState title="Aún no tienes registros" action={<ButtonLink to="/perfil">Agregar mis datos</ButtonLink>}>
            Cada vez que actualices tu peso o tu estatura, aparecerá aquí.
          </EmptyState>
        )}
        {history.isSuccess && history.data.history.length > 0 && (
          <div className="flex flex-col gap-6">
            <WeightChart records={history.data.history} />
            <Card>
              <h2 className="sr-only">Registros</h2>
              <ol className="divide-y divide-line">
                {history.data.history.map((r) => (
                  <li key={r.id} className="flex items-center justify-between gap-3 py-3">
                    <span className="text-muted">{formatDateFromTimestamp(r.recorded_at)}</span>
                    <span className="flex gap-4 text-right font-bold">
                      <span>{r.weight_kg !== null ? `${r.weight_kg} kg` : "Sin peso"}</span>
                      <span>{r.height_cm !== null ? `${r.height_cm} cm` : "Sin estatura"}</span>
                    </span>
                  </li>
                ))}
              </ol>
            </Card>
          </div>
        )}
      </div>
    </Page>
  );
}

/** Línea simple del peso en el tiempo (solo con 2 o más registros con peso). */
function WeightChart({ records }: { records: PhysicalMeasurement[] }) {
  const points = records
    .filter((r): r is PhysicalMeasurement & { weight_kg: number } => r.weight_kg !== null)
    .slice()
    .reverse(); // la API entrega el más reciente primero
  if (points.length < 2) return null;

  const width = 320;
  const height = 140;
  const pad = 24;
  const weights = points.map((p) => p.weight_kg);
  const min = Math.min(...weights);
  const max = Math.max(...weights);
  const span = max - min || 1;
  const x = (i: number) => pad + (i * (width - pad * 2)) / (points.length - 1);
  const y = (w: number) => height - pad - ((w - min) / span) * (height - pad * 2);
  const path = points.map((p, i) => `${i === 0 ? "M" : "L"}${x(i).toFixed(1)},${y(p.weight_kg).toFixed(1)}`).join(" ");
  const first = points[0]!;
  const last = points[points.length - 1]!;

  return (
    <Card>
      <h2 className="text-lg font-bold">Tu peso en el tiempo</h2>
      <p className="text-sm text-muted">
        De {first.weight_kg} kg ({formatShortFromTimestamp(first.recorded_at)}) a {last.weight_kg} kg ({formatShortFromTimestamp(last.recorded_at)}).
      </p>
      <svg viewBox={`0 0 ${width} ${height}`} className="mt-3 w-full" role="img" aria-label={`Peso de ${first.weight_kg} a ${last.weight_kg} kilogramos`}>
        <line x1={pad} x2={width - pad} y1={height - pad} y2={height - pad} stroke="var(--c-line)" strokeWidth="1" />
        <path d={path} fill="none" stroke="var(--c-primary)" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
        {points.map((p, i) => (
          <circle key={p.id} cx={x(i)} cy={y(p.weight_kg)} r="4" fill="var(--c-surface)" stroke="var(--c-primary)" strokeWidth="2.5" />
        ))}
        <text x={pad} y={height - 6} fontSize="11" fill="var(--c-muted)">{formatShortFromTimestamp(first.recorded_at)}</text>
        <text x={width - pad} y={height - 6} fontSize="11" fill="var(--c-muted)" textAnchor="end">{formatShortFromTimestamp(last.recorded_at)}</text>
      </svg>
    </Card>
  );
}
