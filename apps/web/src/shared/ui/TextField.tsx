import { forwardRef, useId, useState, type InputHTMLAttributes, type ReactNode } from "react";
import { cx } from "../lib/cx";

interface TextFieldProps extends Omit<InputHTMLAttributes<HTMLInputElement>, "size"> {
  label: string;
  hint?: ReactNode;
  error?: string;
  /** Muestra "n/max" (por ejemplo, para el apodo). */
  counter?: { value: number; max: number };
  suffix?: ReactNode;
}

export const inputClass = (invalid: boolean) =>
  cx(
    "block w-full min-h-12 rounded-[var(--radius-control)] border-2 bg-surface px-4 py-2.5 text-ink",
    "placeholder:text-muted/70 focus:outline-none focus-visible:outline-3 focus-visible:outline-focus",
    invalid ? "border-danger" : "border-line focus:border-ink/50",
  );

export const TextField = forwardRef<HTMLInputElement, TextFieldProps>(function TextField(
  { label, hint, error, counter, suffix, id, className, ...rest },
  ref,
) {
  const autoId = useId();
  const inputId = id ?? autoId;
  const hintId = `${inputId}-hint`;
  const errorId = `${inputId}-error`;
  const describedBy = [hint ? hintId : null, error ? errorId : null].filter(Boolean).join(" ") || undefined;
  return (
    <div className={cx("flex flex-col gap-1.5", className)}>
      <div className="flex items-baseline justify-between gap-3">
        <label htmlFor={inputId} className="font-bold">
          {label}
        </label>
        {counter && (
          <span className={cx("text-sm tabular-nums", counter.value > counter.max ? "text-danger" : "text-muted")} aria-hidden="true">
            {counter.value}/{counter.max}
          </span>
        )}
      </div>
      <div className="relative">
        <input
          ref={ref}
          id={inputId}
          aria-invalid={error ? true : undefined}
          aria-describedby={describedBy}
          className={cx(inputClass(Boolean(error)), suffix ? "pr-14" : undefined)}
          {...rest}
        />
        {suffix && <div className="absolute inset-y-0 right-1 flex items-center">{suffix}</div>}
      </div>
      {hint && (
        <p id={hintId} className="text-sm text-muted">
          {hint}
        </p>
      )}
      {error && (
        <p id={errorId} className="text-sm font-bold text-danger">
          {error}
        </p>
      )}
    </div>
  );
});

interface PasswordFieldProps extends Omit<TextFieldProps, "type" | "suffix"> {
  /** Indicador de longitud mínima (registro). En el login no aplica. */
  minLength?: number;
  valueLength?: number;
}

export const PasswordField = forwardRef<HTMLInputElement, PasswordFieldProps>(function PasswordField(
  { minLength, valueLength, hint, ...rest },
  ref,
) {
  const [visible, setVisible] = useState(false);
  const lengthHint =
    minLength !== undefined && valueLength !== undefined ? (
      <span className={valueLength >= minLength ? "text-success" : undefined}>
        {valueLength >= minLength ? "Longitud suficiente" : `Mínimo ${minLength} caracteres (${valueLength}/${minLength})`}
      </span>
    ) : null;
  return (
    <TextField
      ref={ref}
      type={visible ? "text" : "password"}
      hint={lengthHint ?? hint}
      suffix={
        <button
          type="button"
          onClick={() => setVisible((v) => !v)}
          className="min-h-10 rounded-lg px-3 text-sm font-bold text-primary-text hover:bg-surface-2"
          aria-pressed={visible}
          aria-label={visible ? "Ocultar contraseña" : "Mostrar contraseña"}
        >
          {visible ? "Ocultar" : "Ver"}
        </button>
      }
      {...rest}
    />
  );
});
