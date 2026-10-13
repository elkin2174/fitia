import { forwardRef, type ButtonHTMLAttributes, type ReactNode } from "react";
import { Link, type LinkProps } from "react-router";
import { cx } from "../lib/cx";
import { Spinner } from "./Spinner";

type Variant = "primary" | "secondary" | "ghost" | "danger";

const base =
  "inline-flex min-h-11 items-center justify-center gap-2 rounded-[var(--radius-control)] px-5 py-2.5 font-bold " +
  "transition-colors disabled:cursor-not-allowed disabled:opacity-55 select-none";
const variants: Record<Variant, string> = {
  primary: "bg-primary text-on-primary hover:bg-primary-strong",
  secondary: "border-2 border-line bg-surface text-ink hover:border-ink/40",
  ghost: "text-primary-text hover:bg-surface-2 px-3",
  danger: "bg-danger text-on-primary hover:opacity-90 dark:text-bg",
};

export function buttonClass(variant: Variant = "primary", fullWidth = false, extra?: string): string {
  return cx(base, variants[variant], fullWidth && "w-full", extra);
}

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  loading?: boolean;
  loadingText?: string;
  fullWidth?: boolean;
  icon?: ReactNode;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = "primary", loading = false, loadingText, fullWidth, icon, className, children, disabled, type, ...rest },
  ref,
) {
  return (
    <button
      ref={ref}
      type={type ?? "button"}
      className={buttonClass(variant, fullWidth, className)}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      {...rest}
    >
      {loading ? <Spinner size={18} /> : icon}
      <span>{loading && loadingText ? loadingText : children}</span>
    </button>
  );
});

interface ButtonLinkProps extends LinkProps {
  variant?: Variant;
  fullWidth?: boolean;
}

export function ButtonLink({ variant = "primary", fullWidth, className, ...rest }: ButtonLinkProps) {
  return <Link className={buttonClass(variant, fullWidth, typeof className === "string" ? className : undefined)} {...rest} />;
}
