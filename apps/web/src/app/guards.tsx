import { Navigate, Outlet, useLocation, useSearchParams } from "react-router";
import { ErrorState, PageSkeleton } from "../shared/ui/Feedback";
import { useQueryClient } from "@tanstack/react-query";
import { safeReturnPath, sessionEndNotice, useMe } from "../shared/session/session";

function SessionLoading() {
  return (
    <div className="mx-auto w-full max-w-xl px-4 py-10">
      <PageSkeleton label="Cargando tu sesión…" />
    </div>
  );
}

function useSessionGate() {
  const me = useMe();
  const location = useLocation();
  const client = useQueryClient();
  const loginPath = `/iniciar-sesion?volver=${encodeURIComponent(location.pathname + location.search)}`;
  return { me, loginPath, ended: sessionEndNotice(client) };
}

/** Sin sesión: al login (guardando la ruta) o, si el usuario cerró sesión a propósito, a la bienvenida. */
function NoSession({ loginPath, ended }: { loginPath: string; ended: string | null }) {
  return ended ? <Navigate to="/" replace state={{ notice: ended }} /> : <Navigate to={loginPath} replace />;
}

/** Login y registro: con sesión activa, se va directo a donde corresponde. */
export function PublicOnly() {
  const me = useMe();
  const [params] = useSearchParams();
  if (me.isPending) return <SessionLoading />;
  if (me.data) {
    const back = safeReturnPath(params.get("volver"));
    return <Navigate to={me.data.onboarding_completed ? (back ?? "/inicio") : "/diagnostico"} replace />;
  }
  return <Outlet />;
}

/** Guard S: requiere sesión. */
export function RequireSession() {
  const { me, loginPath, ended } = useSessionGate();
  if (me.isPending) return <SessionLoading />;
  if (me.isError) return <div className="mx-auto max-w-xl px-4 py-10"><ErrorState message={me.error.message} onRetry={() => me.refetch()} /></div>;
  if (!me.data) return <NoSession loginPath={loginPath} ended={ended} />;
  return <Outlet />;
}

/** Guard S+P: requiere sesión y diagnóstico completo. */
export function RequireProfile() {
  const { me, loginPath, ended } = useSessionGate();
  if (me.isPending) return <SessionLoading />;
  if (me.isError) return <div className="mx-auto max-w-xl px-4 py-10"><ErrorState message={me.error.message} onRetry={() => me.refetch()} /></div>;
  if (!me.data) return <NoSession loginPath={loginPath} ended={ended} />;
  if (!me.data.onboarding_completed) return <Navigate to="/diagnostico" replace />;
  return <Outlet />;
}
