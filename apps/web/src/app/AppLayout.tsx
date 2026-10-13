import { Link, Outlet } from "react-router";
import { BottomNav } from "../shared/ui/BottomNav";
import { Brand } from "../shared/ui/Brand";
import { useMe } from "../shared/session/session";
import { AuthBridge } from "./AuthBridge";

export function AppLayout() {
  const me = useMe();
  const withNav = Boolean(me.data?.onboarding_completed);
  return (
    <div className="min-h-dvh">
      <AuthBridge />
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-50 focus:rounded-lg focus:bg-surface focus:px-4 focus:py-2 focus:font-bold"
      >
        Saltar al contenido
      </a>
      <header className="mx-auto flex max-w-xl items-center justify-between px-4 pt-4 sm:max-w-2xl">
        <Brand to={withNav ? "/inicio" : "/"} />
        {me.data === null && (
          <Link to="/iniciar-sesion" className="min-h-11 rounded-lg px-3 py-2.5 font-bold text-primary-text hover:bg-surface-2">
            Iniciar sesión
          </Link>
        )}
      </header>
      <main id="main" tabIndex={-1} className={withNav ? "pb-28 outline-none" : "pb-12 outline-none"}>
        <Outlet />
      </main>
      {withNav && <BottomNav />}
    </div>
  );
}

/** Contenedor de página: columna legible en móvil y escritorio. */
export function Page({ children, wide = false }: { children: React.ReactNode; wide?: boolean }) {
  return <div className={`mx-auto w-full px-4 py-6 ${wide ? "max-w-2xl" : "max-w-xl"}`}>{children}</div>;
}
