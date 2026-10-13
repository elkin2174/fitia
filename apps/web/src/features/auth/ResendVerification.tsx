import { useMutation } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { isApiError } from "../../shared/api/client";
import { describeWait } from "../../shared/lib/retryAfter";
import { Banner } from "../../shared/ui/Banner";
import { Button } from "../../shared/ui/Button";
import { TextField } from "../../shared/ui/TextField";
import { authApi } from "./api";

const COOLDOWN_SECONDS = 60;
export const NEUTRAL_RESEND_MESSAGE = "Si hay una cuenta pendiente con ese correo, te enviamos un enlace nuevo.";

function useCountdown() {
  const [remaining, setRemaining] = useState(0);
  useEffect(() => {
    if (remaining <= 0) return;
    const timer = window.setTimeout(() => setRemaining((r) => r - 1), 1000);
    return () => window.clearTimeout(timer);
  }, [remaining]);
  return [remaining, setRemaining] as const;
}

interface ResendVerificationProps {
  /** Correo conocido; si falta, se muestra un campo para escribirlo. */
  email?: string;
  label?: string;
}

/** Reenvío del enlace de verificación con enfriamiento visual de 60 s. El 202 siempre da el mismo mensaje. */
export function ResendVerification({ email, label = "Reenviar enlace" }: ResendVerificationProps) {
  const [typed, setTyped] = useState("");
  const [cooldown, setCooldown] = useCountdown();
  const target = (email ?? typed).trim();
  const mutation = useMutation({
    mutationFn: () => authApi.resendVerification(target),
    onSuccess: () => setCooldown(COOLDOWN_SECONDS),
    onError: (error) => {
      if (isApiError(error, "RATE_LIMITED") && error.retryAfter) setCooldown(Math.ceil(error.retryAfter));
    },
  });

  return (
    <div className="flex flex-col gap-3">
      {email === undefined && (
        <TextField
          label="Tu correo institucional"
          type="email"
          inputMode="email"
          autoComplete="email"
          value={typed}
          onChange={(e) => setTyped(e.target.value)}
          placeholder="nombre.apellido@correounivalle.edu.co"
        />
      )}
      <Button
        variant="secondary"
        onClick={() => mutation.mutate()}
        loading={mutation.isPending}
        loadingText="Enviando…"
        disabled={cooldown > 0 || !target}
      >
        {cooldown > 0 ? `${label} (${cooldown} s)` : label}
      </Button>
      {mutation.isSuccess && <Banner tone="success">{NEUTRAL_RESEND_MESSAGE}</Banner>}
      {mutation.isError && (
        <Banner tone="danger" live="assertive">
          {isApiError(mutation.error, "RATE_LIMITED")
            ? `Hiciste varios intentos seguidos. Intenta de nuevo ${describeWait(mutation.error.retryAfter ?? 60)}.`
            : mutation.error.message}
        </Banner>
      )}
    </div>
  );
}
