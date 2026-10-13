import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate } from "react-router";
import { Page } from "../../app/AppLayout";
import { isApiError } from "../../shared/api/client";
import { useMe, useSessionActions } from "../../shared/session/session";
import { Banner } from "../../shared/ui/Banner";
import { Button } from "../../shared/ui/Button";
import { Card } from "../../shared/ui/Feedback";
import { authApi } from "../auth/api";

export function DeleteAccountPage() {
  const navigate = useNavigate();
  const session = useSessionActions();
  const me = useMe();
  const [understood, setUnderstood] = useState(false);

  const remove = useMutation({
    mutationFn: async () => {
      try {
        await authApi.deleteAccount();
      } catch (error) {
        // 401: la cuenta o la sesión ya no existen; el resultado para el usuario es el mismo.
        if (!(isApiError(error) && error.status === 401)) throw error;
      }
    },
    onSuccess: () => {
      session.clear("account_deleted");
      void navigate("/", { replace: true, state: { notice: "account_deleted" } });
    },
  });

  // "Cancelar" no envía ninguna petición: solo vuelve atrás.
  const cancel = () => navigate(me.data?.onboarding_completed ? "/perfil" : "/diagnostico");

  return (
    <Page>
      <h1 className="text-3xl font-extrabold">Eliminar mi cuenta</h1>
      <Card className="mt-6">
        <h2 className="text-lg font-bold text-danger">Esta acción es definitiva y no se puede deshacer.</h2>
        <p className="mt-3">Al eliminar tu cuenta:</p>
        <ul className="mt-2 list-disc space-y-1.5 pl-5">
          <li>Se borran tu perfil, tu diagnóstico, tu plan, tu historial de peso y estatura, y tus puntos.</li>
          <li>Se cierran tus sesiones en todos tus dispositivos.</li>
          <li>Desapareces del ranking.</li>
          <li>Podrás registrarte de nuevo con el mismo correo, empezando de cero.</li>
        </ul>

        <label className="mt-6 flex min-h-11 cursor-pointer items-start gap-3 font-bold">
          <input
            type="checkbox"
            checked={understood}
            onChange={(e) => setUnderstood(e.target.checked)}
            className="mt-1 size-5 shrink-0 accent-[var(--c-danger)]"
          />
          Entiendo que es definitivo.
        </label>

        {remove.isError && (
          <Banner tone="danger" className="mt-4" live="assertive">
            {remove.error.message}
          </Banner>
        )}

        <div className="mt-6 flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
          <Button variant="secondary" onClick={cancel} disabled={remove.isPending}>
            Cancelar
          </Button>
          <Button variant="danger" disabled={!understood} onClick={() => remove.mutate()} loading={remove.isPending} loadingText="Eliminando…">
            Eliminar mi cuenta
          </Button>
        </div>
      </Card>
    </Page>
  );
}
