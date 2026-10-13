import type { ReactNode } from "react";
import { cx } from "../lib/cx";
import { Banner } from "./Banner";
import { Button } from "./Button";

export function ProgressBar({ value, max, label }: { value: number; max: number; label: string }) {
  return (
    <div>
      <div className="mb-2 flex justify-between text-sm font-bold text-muted">
        <span>{label}</span>
      </div>
      <div
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={max}
        aria-valuenow={value}
        aria-label={label}
        className="h-2.5 overflow-hidden rounded-full bg-surface-2"
      >
        <div className="h-full rounded-full bg-primary transition-[width] duration-300" style={{ width: `${(value / max) * 100}%` }} />
      </div>
    </div>
  );
}

export function Skeleton({ className }: { className?: string }) {
  return <div aria-hidden="true" className={cx("animate-pulse rounded-[var(--radius-control)] bg-surface-2", className)} />;
}

/** Esqueleto de página con texto accesible de carga. */
export function PageSkeleton({ label = "Cargando…", rows = 3 }: { label?: string; rows?: number }) {
  return (
    <div role="status" aria-live="polite" className="flex flex-col gap-4">
      <span className="sr-only">{label}</span>
      <Skeleton className="h-9 w-2/3" />
      {Array.from({ length: rows }, (_, i) => (
        <Skeleton key={i} className="h-24 w-full" />
      ))}
    </div>
  );
}

export function EmptyState({ title, children, action, icon }: { title: string; children?: ReactNode; action?: ReactNode; icon?: ReactNode }) {
  return (
    <div className="flex flex-col items-center gap-3 rounded-[var(--radius-card)] border-2 border-dashed border-line px-6 py-10 text-center">
      {icon && <div aria-hidden="true" className="text-muted">{icon}</div>}
      <p className="font-display text-lg font-bold">{title}</p>
      {children && <div className="max-w-sm text-muted">{children}</div>}
      {action}
    </div>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <Banner
      tone="danger"
      title="No pudimos cargar esta información"
      live="assertive"
      actions={onRetry && <Button variant="secondary" onClick={onRetry}>Reintentar</Button>}
    >
      {message}
    </Banner>
  );
}

export function Card({ children, className, as: Tag = "section", ...rest }: { children: ReactNode; className?: string; as?: "section" | "div" | "article"; "aria-labelledby"?: string; id?: string }) {
  return (
    <Tag className={cx("rounded-[var(--radius-card)] border border-line bg-surface p-5 sm:p-6", className)} {...rest}>
      {children}
    </Tag>
  );
}
