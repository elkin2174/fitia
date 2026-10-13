import { NavLink } from "react-router";
import { cx } from "../lib/cx";

const items = [
  { to: "/inicio", label: "Inicio", icon: "M4 11l8-7 8 7v9a1 1 0 0 1-1 1h-5v-6h-4v6H5a1 1 0 0 1-1-1z" },
  { to: "/ranking", label: "Ranking", icon: "M5 21V11h4v10M10 21V4h4v17M15 21v-7h4v7" },
  { to: "/perfil", label: "Perfil", icon: "M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8zm-8 9a8 8 0 0 1 16 0" },
];

export function BottomNav() {
  return (
    <nav
      aria-label="Navegación principal"
      className="fixed inset-x-0 bottom-0 z-40 border-t border-line bg-surface/95 pb-[env(safe-area-inset-bottom)] backdrop-blur"
    >
      <ul className="mx-auto grid max-w-xl grid-cols-3">
        {items.map((item) => (
          <li key={item.to}>
            <NavLink
              to={item.to}
              className={({ isActive }) =>
                cx(
                  "flex min-h-16 flex-col items-center justify-center gap-1 text-sm font-bold",
                  isActive ? "text-primary-text" : "text-muted hover:text-ink",
                )
              }
            >
              {({ isActive }) => (
                <>
                  <svg width="24" height="24" viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="2" strokeLinejoin="round" strokeLinecap="round">
                    <path d={item.icon} />
                  </svg>
                  <span>{item.label}</span>
                  <span className={cx("h-1 w-6 rounded-full", isActive ? "bg-primary" : "bg-transparent")} aria-hidden="true" />
                </>
              )}
            </NavLink>
          </li>
        ))}
      </ul>
    </nav>
  );
}
