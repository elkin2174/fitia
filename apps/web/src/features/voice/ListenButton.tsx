import { Button } from "../../shared/ui/Button";

export interface ListenButtonProps {
  onListen: () => void;
  isLoading: boolean;
  isPlaying?: boolean;
  isUnavailable?: boolean;
  className?: string;
}

export function ListenButton({
  onListen,
  isLoading,
  isUnavailable = false,
  className,
}: ListenButtonProps) {
  return (
    <div className="flex flex-col gap-2">
      <Button
        variant="primary"
        onClick={onListen}
        loading={isLoading}
        loadingText="Preparando audio…"
        disabled={isLoading || isUnavailable}
        icon={
          <svg
            className="h-5 w-5 shrink-0"
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
        }
        className={className}
      >
        Escuchar
      </Button>
      {isUnavailable && (
        <p className="text-sm text-muted" role="status">
          Tu dispositivo no tiene voz en español disponible. Puedes leer la explicación en pantalla.
        </p>
      )}
    </div>
  );
}
