import { useMutation } from "@tanstack/react-query";
import { useEffect, useRef } from "react";
import { useNavigate, useSearchParams } from "react-router";
import { Page } from "../../app/AppLayout";
import { isApiError } from "../../shared/api/client";
import { useMe, useSessionActions } from "../../shared/session/session";
import { Banner } from "../../shared/ui/Banner";
import { Button, ButtonLink } from "../../shared/ui/Button";
import { Spinner } from "../../shared/ui/Spinner";
import { authApi } from "./api";
import { ResendVerification } from "./ResendVerification";

const REDIRECT_MS = 1800;

export function VerifyEmailPage() {
  const [params] = useSearchParams();
  const token = params.get("token");
  const navigate = useNavigate();
  const session = useSessionActions();
  const me = useMe();
  const started = useRef(false);

  const verify = useMutation({
    mutationFn: (value: string) => authApi.verifyEmail(value),
    onSuccess: async (result) => {
      // La respuesta ya crea la sesión (cookie): el diagnóstico es lo siguiente.
      await session.setUser(result.user, false);
      window.setTimeout(() => navigate("/diagnostico", { replace: true }), REDIRECT_MS);
    },
  });

  useEffect(() => {
    // Un único POST, también con React StrictMode (que ejecuta los efectos dos veces en desarrollo).
    if (!token || started.current) return;
    started.current = true;
    verify.mutate(token);
  }, [token]);

  const hasSession = Boolean(me.data);

  return (
    <Page>
      <h1 className="text-3xl font-extrabold">Verificación de tu correo</h1>
      <div className="mt-6" aria-live="polite">
        {!token && (
          <div className="flex flex-col gap-5">
            <Banner tone="warn" title="Este enlace no es válido.">
              Abre el enlace completo que te enviamos por correo, o pide uno nuevo.
            </Banner>
            <ResendVerification label="Enviarme un enlace nuevo" />
          </div>
        )}

        {token && (verify.isPending || verify.isIdle) && (
          <p className="flex items-center gap-3 text-lg">
            <Spinner /> Estamos verificando tu correo…
          </p>
        )}

        {verify.isSuccess && (
          <Banner tone="success" title={`¡Listo, ${verify.data.user.nickname}! Tu correo quedó verificado.`}
            actions={<ButtonLink to="/diagnostico" replace>Continuar</ButtonLink>}>
            Ahora cuéntanos un poco de ti para armar tu plan. Te llevamos en un momento.
          </Banner>
        )}

        {verify.isError && isApiError(verify.error, "TOKEN_EXPIRED_OR_USED") && (
          <div className="flex flex-col gap-5">
            <Banner tone="warn" title="Este enlace venció o ya se usó." live="assertive">
              {verify.error.message}
            </Banner>
            {hasSession ? (
              <ButtonLink to={me.data?.onboarding_completed ? "/inicio" : "/diagnostico"}>Ir a FITIA</ButtonLink>
            ) : (
              <ResendVerification label="Enviarme un enlace nuevo" />
            )}
          </div>
        )}

        {verify.isError && !isApiError(verify.error, "TOKEN_EXPIRED_OR_USED") && (
          <Banner
            tone="danger"
            title="No pudimos verificar tu correo."
            live="assertive"
            actions={<Button variant="secondary" onClick={() => token && verify.mutate(token)}>Reintentar</Button>}
          >
            {verify.error.message}
          </Banner>
        )}
      </div>
    </Page>
  );
}
