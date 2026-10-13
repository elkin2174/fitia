import type { ReactNode } from "react";
import { cx } from "../lib/cx";

type Tone = "info" | "success" | "warn" | "danger";

const tones: Record<Tone, { box: string; icon: string; glyph: string }> = {
  info: { box: "bg-info-soft border-info/40", icon: "text-info", glyph: "i" },
  success: { box: "bg-success-soft border-success/40", icon: "text-success", glyph: "✓" },
  warn: { box: "bg-warn-soft border-warn/40", icon: "text-warn", glyph: "!" },
  danger: { box: "bg-danger-soft border-danger/40", icon: "text-danger", glyph: "!" },
};

interface BannerProps {
  tone?: Tone;
  title?: ReactNode;
  children?: ReactNode;
  actions?: ReactNode;
  /** "alert" interrumpe al lector de pantalla; úsalo para errores que bloquean. */
  live?: "polite" | "assertive" | "off";
  className?: string;
}

export function Banner({ tone = "info", title, children, actions, live = "polite", className }: BannerProps) {
  const t = tones[tone];
  return (
    <div
      role={live === "assertive" ? "alert" : live === "polite" ? "status" : undefined}
      className={cx("flex gap-3 rounded-[var(--radius-control)] border-2 p-4", t.box, className)}
    >
      <span
        aria-hidden="true"
        className={cx("grid size-6 shrink-0 place-items-center rounded-full border-2 border-current text-sm font-bold", t.icon)}
      >
        {t.glyph}
      </span>
      <div className="flex min-w-0 flex-1 flex-col gap-1">
        {title && <p className="font-bold">{title}</p>}
        {children && <div className="text-[0.975rem]">{children}</div>}
        {actions && <div className="mt-2 flex flex-wrap gap-2">{actions}</div>}
      </div>
    </div>
  );
}
