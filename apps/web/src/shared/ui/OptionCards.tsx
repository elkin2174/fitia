import { useId, useRef, type KeyboardEvent } from "react";
import type { OptionCode, QuestionOption } from "../api/types";
import { cx } from "../lib/cx";

/** Compara códigos respetando su tipo JSON (4 !== "4", true !== "true"). */
export const sameCode = (a: OptionCode | null | undefined, b: OptionCode) => a === b && typeof a === typeof b;

interface OptionCardsProps {
  legend: string;
  hideLegend?: boolean;
  options: QuestionOption[];
  value: OptionCode | null;
  onChange: (code: OptionCode) => void;
  error?: string;
  columns?: 1 | 2;
}

/** Grupo de radio con tarjetas grandes y tocables (patrón ARIA radiogroup con flechas). */
export function OptionCards({ legend, hideLegend, options, value, onChange, error, columns = 1 }: OptionCardsProps) {
  const id = useId();
  const refs = useRef<Array<HTMLButtonElement | null>>([]);
  const selectedIndex = options.findIndex((o) => sameCode(value, o.code));

  const onKeyDown = (event: KeyboardEvent<HTMLButtonElement>, index: number) => {
    const delta = event.key === "ArrowDown" || event.key === "ArrowRight" ? 1 : event.key === "ArrowUp" || event.key === "ArrowLeft" ? -1 : 0;
    if (!delta) return;
    event.preventDefault();
    const next = (index + delta + options.length) % options.length;
    const option = options[next];
    if (option) {
      onChange(option.code);
      refs.current[next]?.focus();
    }
  };

  return (
    <div className="flex flex-col gap-2">
      <p id={`${id}-legend`} className={hideLegend ? "sr-only" : "font-bold"}>
        {legend}
      </p>
      <div
        role="radiogroup"
        aria-labelledby={`${id}-legend`}
        aria-describedby={error ? `${id}-error` : undefined}
        aria-invalid={error ? true : undefined}
        className={cx("grid gap-3", columns === 2 && "sm:grid-cols-2")}
      >
        {options.map((option, index) => {
          const checked = sameCode(value, option.code);
          return (
            <button
              key={String(option.code)}
              ref={(el) => {
                refs.current[index] = el;
              }}
              type="button"
              role="radio"
              aria-checked={checked}
              tabIndex={checked || (selectedIndex === -1 && index === 0) ? 0 : -1}
              onClick={() => onChange(option.code)}
              onKeyDown={(e) => onKeyDown(e, index)}
              className={cx(
                "flex min-h-14 items-center gap-3 rounded-[var(--radius-control)] border-2 px-4 py-3 text-left font-bold transition-colors",
                checked ? "border-primary bg-primary/8 text-ink" : "border-line bg-surface hover:border-ink/40",
              )}
            >
              <span
                aria-hidden="true"
                className={cx(
                  "grid size-6 shrink-0 place-items-center rounded-full border-2",
                  checked ? "border-primary bg-primary" : "border-line",
                )}
              >
                {checked && <span className="size-2.5 rounded-full bg-on-primary" />}
              </span>
              {option.label}
            </button>
          );
        })}
      </div>
      {error && (
        <p id={`${id}-error`} role="alert" className="text-sm font-bold text-danger">
          {error}
        </p>
      )}
    </div>
  );
}
