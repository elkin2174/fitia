import { useId } from "react";
import type { QuestionOption } from "../api/types";
import { cx } from "../lib/cx";
import { WEEKDAY_SHORT } from "../lib/dates";

interface DayChipsProps {
  legend: string;
  hideLegend?: boolean;
  options: QuestionOption[];
  value: number[];
  onChange: (days: number[]) => void;
  error?: string;
}

/** Selección múltiple de días (L M X J V). Las etiquetas completas vienen del cuestionario. */
export function DayChips({ legend, hideLegend, options, value, onChange, error }: DayChipsProps) {
  const id = useId();
  const toggle = (day: number) =>
    onChange(value.includes(day) ? value.filter((d) => d !== day) : [...value, day].sort((a, b) => a - b));
  return (
    <fieldset className="flex flex-col gap-2" aria-describedby={error ? `${id}-error` : undefined}>
      <legend className={hideLegend ? "sr-only" : "mb-2 font-bold"}>{legend}</legend>
      <div className="grid grid-cols-5 gap-2">
        {options.map((option) => {
          const day = option.code as number;
          const checked = value.includes(day);
          return (
            <button
              key={day}
              type="button"
              role="checkbox"
              aria-checked={checked}
              aria-label={option.label}
              onClick={() => toggle(day)}
              className={cx(
                "flex min-h-16 flex-col items-center justify-center rounded-[var(--radius-control)] border-2 font-display",
                checked ? "border-primary bg-primary text-on-primary" : "border-line bg-surface text-ink hover:border-ink/40",
              )}
            >
              <span className="text-2xl font-bold leading-none" aria-hidden="true">
                {WEEKDAY_SHORT[day] ?? option.label.charAt(0)}
              </span>
              <span className="mt-1 text-xs font-sans" aria-hidden="true">
                {option.label.slice(0, 3)}
              </span>
            </button>
          );
        })}
      </div>
      {error && (
        <p id={`${id}-error`} className="text-sm font-bold text-danger">
          {error}
        </p>
      )}
    </fieldset>
  );
}
