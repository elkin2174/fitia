import { useQuery } from "@tanstack/react-query";
import { useCallback, useEffect, useState } from "react";
import { Link, useBlocker } from "react-router";
import { Page } from "../../app/AppLayout";
import { useMe } from "../../shared/session/session";
import { Button } from "../../shared/ui/Button";
import { ConfirmDialog } from "../../shared/ui/ConfirmDialog";
import { Card, ErrorState, PageSkeleton } from "../../shared/ui/Feedback";
import { useLogout } from "../auth/useLogout";
import { profileApi, profileKey } from "./api";
import { PhysicalSection } from "./PhysicalSection";
import { PrivacySection } from "./PrivacySection";
import { ProfileDiagnosticView } from "./ProfileDiagnosticView";

export function ProfilePage() {
  const me = useMe();
  const profile = useQuery({ queryKey: profileKey, queryFn: () => profileApi.get() });
  const logout = useLogout();

  // Cambios sin guardar en cualquier sección → confirmar antes de salir (AC-7-3).
  const [dirtySections, setDirtySections] = useState<Record<string, boolean>>({});
  const markDirty = useCallback((section: string) => (dirty: boolean) => {
    setDirtySections((prev) => (prev[section] === dirty ? prev : { ...prev, [section]: dirty }));
  }, []);
  const onDiagnosticDirty = useCallback((d: boolean) => markDirty("diagnostic")(d), [markDirty]);
  const onPhysicalDirty = useCallback((d: boolean) => markDirty("physical")(d), [markDirty]);
  const dirty = Object.values(dirtySections).some(Boolean);
  const blocker = useBlocker(dirty);

  useEffect(() => {
    if (!dirty) return;
    const onBeforeUnload = (e: BeforeUnloadEvent) => e.preventDefault();
    window.addEventListener("beforeunload", onBeforeUnload);
    return () => window.removeEventListener("beforeunload", onBeforeUnload);
  }, [dirty]);

  if (profile.isPending) {
    return (
      <Page>
        <PageSkeleton label="Cargando tu perfil…" rows={4} />
      </Page>
    );
  }
  if (profile.isError) {
    return (
      <Page>
        <ErrorState message={profile.error.message} onRetry={() => profile.refetch()} />
      </Page>
    );
  }

  const data = profile.data.profile;
  const noPoints = data.points === 0;

  return (
    <Page>
      <header>
        <h1 className="text-3xl font-extrabold">{me.data?.nickname}</h1>
        <p className="mt-1 text-muted">{me.data?.program.name}</p>
      </header>

      <Card className="mt-6" aria-labelledby="progress-title">
        <h2 id="progress-title" className="sr-only">
          Tu progreso
        </h2>
        <dl className="grid grid-cols-3 text-center">
          <div>
            <dt className="text-sm text-muted">Nivel</dt>
            <dd className="font-display text-3xl font-extrabold">{data.level}</dd>
          </div>
          <div className="border-x border-line">
            <dt className="text-sm text-muted">Puntos</dt>
            <dd className="font-display text-3xl font-extrabold">{data.points}</dd>
          </div>
          <div>
            <dt className="text-sm text-muted">Posición</dt>
            <dd className="font-display text-3xl font-extrabold">{data.ranking_position ? `#${data.ranking_position}` : "—"}</dd>
          </div>
        </dl>
        {noPoints && (
          <p className="mt-4 text-center text-muted">
            Completa entrenamientos para sumar puntos y subir de nivel. <Link to="/ranking" className="font-bold text-primary-text underline">Ver ranking</Link>
          </p>
        )}
      </Card>

      <div className="mt-6 flex flex-col gap-6">
        <ProfileDiagnosticView profile={data} onDirtyChange={onDiagnosticDirty} />
        <PhysicalSection profile={data} onDirtyChange={onPhysicalDirty} />
        <PrivacySection profile={data} />

        <Card aria-labelledby="account-title">
          <h2 id="account-title" className="text-xl font-bold">
            Cuenta
          </h2>
          <Button variant="secondary" className="mt-4" onClick={() => logout.mutate()} loading={logout.isPending} loadingText="Cerrando sesión…">
            Cerrar sesión
          </Button>
          <div className="mt-6 rounded-[var(--radius-control)] border-2 border-danger/40 p-4">
            <h3 className="font-bold text-danger">Zona de peligro</h3>
            <p className="mt-1 text-sm text-muted">Eliminar tu cuenta borra todos tus datos de forma definitiva.</p>
            <Link to="/perfil/eliminar-cuenta" className="mt-3 inline-flex min-h-11 items-center font-bold text-danger underline">
              Eliminar mi cuenta
            </Link>
          </div>
        </Card>
      </div>

      <ConfirmDialog
        open={blocker.state === "blocked"}
        title="¿Descartar los cambios?"
        confirmLabel="Salir sin guardar"
        cancelLabel="Seguir editando"
        onConfirm={() => blocker.proceed?.()}
        onCancel={() => blocker.reset?.()}
      >
        Tienes cambios sin guardar en tu perfil. Si sales, se pierden.
      </ConfirmDialog>
    </Page>
  );
}
