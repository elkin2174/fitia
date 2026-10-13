import { useEffect, useRef, useState } from "react";
import { Link } from "react-router";
import { useLogout } from "../auth/useLogout";

/** Menú de cuenta para pantallas sin barra de navegación (por ejemplo, el diagnóstico). */
export function AccountMenu() {
  const [open, setOpen] = useState(false);
  const logout = useLogout();
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (!ref.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, [open]);

  return (
    <div ref={ref} className="relative shrink-0" onKeyDown={(e) => e.key === "Escape" && setOpen(false)}>
      <button
        type="button"
        aria-expanded={open}
        aria-haspopup="true"
        onClick={() => setOpen((o) => !o)}
        className="min-h-11 rounded-lg border-2 border-line px-3 font-bold hover:bg-surface-2"
      >
        Cuenta
      </button>
      {open && (
        <div className="absolute right-0 z-30 mt-2 w-56 rounded-[var(--radius-control)] border-2 border-line bg-surface p-1 shadow-raised">
          <button
            type="button"
            onClick={() => logout.mutate()}
            disabled={logout.isPending}
            className="block min-h-11 w-full rounded-lg px-3 text-left font-bold hover:bg-surface-2"
          >
            {logout.isPending ? "Cerrando sesión…" : "Cerrar sesión"}
          </button>
          <Link to="/perfil/eliminar-cuenta" className="flex min-h-11 items-center rounded-lg px-3 font-bold text-danger hover:bg-surface-2">
            Eliminar mi cuenta
          </Link>
        </div>
      )}
    </div>
  );
}
