import { useEffect, useId, useRef, type ReactNode } from "react";

export interface BottomSheetProps {
  open: boolean;
  title: string;
  children: ReactNode;
  onClose: () => void;
  closeLabel?: string;
}

/**
 * Hoja inferior accesible (role="dialog", aria-modal="true").
 * Atrapa el foco, cierra con Escape y al tocar el fondo, y devuelve el foco al elemento que la abrió.
 */
export function BottomSheet({
  open,
  title,
  children,
  onClose,
  closeLabel = "Cerrar explicación",
}: BottomSheetProps) {
  const id = useId();
  const closeButtonRef = useRef<HTMLButtonElement>(null);
  const sheetRef = useRef<HTMLDivElement>(null);
  const previousActiveElement = useRef<Element | null>(null);

  useEffect(() => {
    if (!open) return;
    previousActiveElement.current = document.activeElement;
    // Dar foco al botón de cerrar inmediatamente
    closeButtonRef.current?.focus();

    return () => {
      (previousActiveElement.current as HTMLElement | null)?.focus?.();
    };
  }, [open]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-end justify-center bg-ink/50 backdrop-blur-xs p-0 sm:items-center sm:p-4"
      onClick={(e) => {
        if (e.target === e.currentTarget) {
          onClose();
        }
      }}
    >
      <div
        ref={sheetRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={`${id}-sheet-title`}
        className="w-full max-w-lg max-h-[85vh] flex flex-col rounded-t-[var(--radius-card)] sm:rounded-[var(--radius-card)] bg-surface p-6 shadow-raised border-t-2 sm:border-2 border-line animate-in fade-in slide-in-from-bottom duration-200 motion-reduce:animate-none"
        onKeyDown={(e) => {
          if (e.key === "Escape") {
            e.stopPropagation();
            onClose();
          }
          if (e.key === "Tab") {
            const focusables = sheetRef.current?.querySelectorAll<HTMLElement>(
              'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
            );
            if (!focusables?.length) return;
            const first = focusables[0]!;
            const last = focusables[focusables.length - 1]!;
            if (e.shiftKey && document.activeElement === first) {
              e.preventDefault();
              last.focus();
            } else if (!e.shiftKey && document.activeElement === last) {
              e.preventDefault();
              first.focus();
            }
          }
        }}
      >
        {/* Barra superior de arrastre / decoración táctil */}
        <div className="mx-auto mb-3 h-1.5 w-12 rounded-full bg-line" aria-hidden="true" />

        <div className="flex items-start justify-between gap-4 border-b border-line pb-4">
          <h2 id={`${id}-sheet-title`} className="text-xl font-bold leading-tight">
            {title}
          </h2>
          <button
            ref={closeButtonRef}
            type="button"
            aria-label={closeLabel}
            onClick={onClose}
            className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full text-muted hover:bg-surface-2 hover:text-ink focus-visible:outline-2 focus-visible:outline-focus transition-colors cursor-pointer"
          >
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
                d="M6 18L18 6M6 6l12 12"
              />
            </svg>
          </button>
        </div>

        <div className="mt-4 overflow-y-auto flex-1 text-ink">{children}</div>
      </div>
    </div>
  );
}
