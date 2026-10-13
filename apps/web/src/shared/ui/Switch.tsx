import { useId, type ReactNode } from "react";
import { cx } from "../lib/cx";

interface SwitchProps {
  label: string;
  description?: ReactNode;
  checked: boolean;
  onChange: (checked: boolean) => void;
  disabled?: boolean;
}

export function Switch({ label, description, checked, onChange, disabled }: SwitchProps) {
  const id = useId();
  return (
    <div className="flex items-start justify-between gap-4">
      <div>
        <p id={`${id}-label`} className="font-bold">
          {label}
        </p>
        {description && (
          <div id={`${id}-desc`} className="mt-1 text-sm text-muted">
            {description}
          </div>
        )}
      </div>
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        aria-labelledby={`${id}-label`}
        aria-describedby={description ? `${id}-desc` : undefined}
        disabled={disabled}
        onClick={() => onChange(!checked)}
        className={cx(
          "relative mt-0.5 inline-flex h-8 w-14 shrink-0 items-center rounded-full border-2 transition-colors disabled:opacity-55 cursor-pointer",
          "before:absolute before:-inset-2 before:content-['']",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus focus-visible:ring-offset-2",
          checked ? "border-rest bg-rest" : "border-line bg-surface-2",
        )}
      >
        <span
          aria-hidden="true"
          className={cx(
            "inline-block size-6 rounded-full bg-surface shadow transition-transform",
            checked ? "translate-x-6" : "translate-x-0.5",
          )}
        />
        <span className="sr-only">{checked ? "Activado" : "Desactivado"}</span>
      </button>
    </div>
  );
}
