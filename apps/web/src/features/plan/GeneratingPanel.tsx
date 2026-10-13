import { useEffect, useState } from "react";
import { Button } from "../../shared/ui/Button";
import { ROTATING_MESSAGES } from "./usePlanGeneration";

export interface GeneratingPanelProps {
  slow: boolean;
  onKeepWaiting: () => void;
  onRetry: () => void;
  retrying: boolean;
}

export function GeneratingPanel({
  slow,
  onKeepWaiting,
  onRetry,
  retrying,
}: GeneratingPanelProps) {
  const [index, setIndex] = useState(0);
  useEffect(() => {
    const timer = window.setInterval(
      () => setIndex((i) => (i + 1) % ROTATING_MESSAGES.length),
      4000
    );
    return () => window.clearInterval(timer);
  }, []);

  return (
    <section
      className="rounded-[var(--radius-card)] border-2 border-line bg-surface p-6"
      aria-labelledby="generating-title"
    >
      <h2 id="generating-title" className="text-2xl font-bold">
        Estamos armando tu plan…
      </h2>
      <p role="status" className="sr-only">
        Estamos armando tu plan. Te avisaremos cuando esté listo.
      </p>
      <div
        className="relative mt-5 h-3 overflow-hidden rounded-full bg-surface-2"
        aria-hidden="true"
      >
        <div className="animate-runner absolute inset-y-0 w-1/4 rounded-full bg-primary" />
      </div>
      <p className="mt-4 min-h-12 text-muted" aria-hidden="true">
        {ROTATING_MESSAGES[index]}
      </p>
      <p className="text-sm text-muted">
        Puedes seguir usando la app; te mostramos el plan apenas esté listo.
      </p>
      {slow && (
        <div
          className="mt-5 flex flex-col gap-3 border-t border-line pt-5"
          role="status"
        >
          <p className="font-bold">Está tardando más de lo normal.</p>
          <div className="flex flex-wrap gap-2">
            <Button variant="secondary" onClick={onKeepWaiting}>
              Seguir esperando
            </Button>
            <Button onClick={onRetry} loading={retrying} loadingText="Reintentando…">
              Reintentar
            </Button>
          </div>
        </div>
      )}
    </section>
  );
}
