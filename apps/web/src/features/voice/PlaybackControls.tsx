import { Banner } from "../../shared/ui/Banner";
import { Button } from "../../shared/ui/Button";
import { PLAYBACK_RATES, type PlaybackRate } from "./playbackRate";

export interface PlaybackControlsProps {
  hasAudio: boolean;
  isPlaying: boolean;
  isPaused: boolean;
  isLoading: boolean;
  rate: PlaybackRate;
  error: Error | null;
  onPlay: () => void;
  onPause: () => void;
  onResume: () => void;
  onRestart: () => void;
  onRateChange: (rate: PlaybackRate) => void;
  onRetry: () => void;
}

export function PlaybackControls({
  hasAudio,
  isPlaying,
  isPaused,
  isLoading,
  rate,
  error,
  onPlay,
  onPause,
  onResume,
  onRestart,
  onRateChange,
  onRetry,
}: PlaybackControlsProps) {
  const isControlsDisabled = !hasAudio || isLoading;

  return (
    <div className="flex flex-col gap-3 rounded-[var(--radius-control)] border-2 border-line bg-surface-2 p-3">
      {/* Estado de error con reintento (HU 3) */}
      {error && (
        <Banner
          tone="danger"
          title="No pudimos generar el audio"
          live="assertive"
          actions={
            <Button
              variant="secondary"
              onClick={onRetry}
              disabled={isLoading}
            >
              Reintentar
            </Button>
          }
        >
          {error.message || "Ocurrió un error al preparar la explicación hablada."}
          {/*
            PUNTO DE EXTENSIÓN PARA HU 6 (Respaldo con voz del navegador):
            Cuando el servicio de audio IA falle (503 AI_UNAVAILABLE o error de red),
            aquí se activará el sintetizador nativo window.speechSynthesis como
            mecanismo de respaldo transparente para el estudiante.
          */}
        </Banner>
      )}

      <div className="flex flex-wrap items-center justify-between gap-3">
        {/* Controles de reproducción: Pausar/Reanudar y Repetir (HU 4) */}
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={isPlaying ? onPause : isPaused ? onResume : onPlay}
            disabled={isControlsDisabled}
            aria-label={isPlaying ? "Pausar" : "Reanudar"}
            className="inline-flex min-h-11 min-w-11 items-center justify-center gap-2 rounded-[var(--radius-control)] border-2 border-line bg-surface px-4 py-2 font-bold text-ink transition-colors hover:border-ink/40 disabled:cursor-not-allowed disabled:opacity-50 focus-visible:outline-2 focus-visible:outline-focus cursor-pointer"
          >
            {isPlaying ? (
              <>
                <svg className="h-5 w-5 shrink-0" fill="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                  <path d="M6 4h4v16H6V4zm8 0h4v16h-4V4z" />
                </svg>
                <span>Pausar</span>
              </>
            ) : (
              <>
                <svg className="h-5 w-5 shrink-0" fill="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                  <path d="M8 5v14l11-7z" />
                </svg>
                <span>Reanudar</span>
              </>
            )}
          </button>

          <button
            type="button"
            onClick={onRestart}
            disabled={isControlsDisabled}
            aria-label="Repetir"
            className="inline-flex min-h-11 min-w-11 items-center justify-center gap-2 rounded-[var(--radius-control)] border-2 border-line bg-surface px-4 py-2 font-bold text-ink transition-colors hover:border-ink/40 disabled:cursor-not-allowed disabled:opacity-50 focus-visible:outline-2 focus-visible:outline-focus cursor-pointer"
          >
            <svg className="h-5 w-5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
              />
            </svg>
            <span>Repetir</span>
          </button>
        </div>

        {/* Selector de velocidad (HU 5) */}
        <div
          role="group"
          aria-label="Velocidad de reproducción"
          className="flex items-center gap-1"
        >
          {PLAYBACK_RATES.map((r) => {
            const isSelected = rate === r;
            const label = r === 0.75 ? "0,75×" : r === 1 ? "1×" : "1,25×";
            return (
              <button
                key={r}
                type="button"
                onClick={() => onRateChange(r)}
                aria-pressed={isSelected}
                aria-label={`Velocidad ${label}`}
                className={
                  "inline-flex min-h-11 min-w-11 items-center justify-center rounded-[var(--radius-control)] border-2 px-2.5 py-1 text-sm font-bold transition-colors focus-visible:outline-2 focus-visible:outline-focus cursor-pointer " +
                  (isSelected
                    ? "border-primary bg-primary text-on-primary"
                    : "border-line bg-surface text-ink hover:border-ink/40")
                }
              >
                {label}
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}
