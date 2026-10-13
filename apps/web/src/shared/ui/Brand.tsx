import { Link } from "react-router";

export function TrackMark({ size = 28 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden="true">
      <rect width="32" height="32" rx="8" fill="var(--c-primary)" />
      <path d="M6 22c4-9 16-9 20 0M6 17c4-6 16-6 20 0" fill="none" stroke="#fff" strokeWidth="2.4" strokeLinecap="round" />
    </svg>
  );
}

export function Brand({ to = "/" }: { to?: string }) {
  return (
    <Link to={to} className="inline-flex min-h-11 items-center gap-2 rounded-lg font-display text-xl font-extrabold tracking-tight">
      <TrackMark />
      <span>FITIA</span>
    </Link>
  );
}
