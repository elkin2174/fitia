import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { Link, useNavigate, useSearchParams } from "react-router";
import { z } from "zod";
import { Page } from "../../app/AppLayout";
import { isApiError } from "../../shared/api/client";
import { fieldMessage } from "../../shared/lib/fieldErrors";
import { describeWait } from "../../shared/lib/retryAfter";
import { safeReturnPath, useSessionActions } from "../../shared/session/session";
import { Banner } from "../../shared/ui/Banner";
import { Button, ButtonLink } from "../../shared/ui/Button";
import { PasswordField, TextField } from "../../shared/ui/TextField";
import { authApi } from "./api";
import { ResendVerification } from "./ResendVerification";

// En el login no aplica el mínimo de 8 caracteres (solo en el registro).
const schema = z.object({
  email: z
    .string()
    .transform((v) => v.trim())
    .pipe(z.string().regex(/^[^@\s]+@[^@\s]+\.[^@\s]+$/, fieldMessage("email", "INVALID_EMAIL"))),
  password: z.string().min(1, fieldMessage("password", "REQUIRED")).max(128, fieldMessage("password", "PASSWORD_TOO_LONG")),
});
type FormInput = z.input<typeof schema>;
type FormOutput = z.output<typeof schema>;

export function LoginPage() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const session = useSessionActions();
  const [lockedFor, setLockedFor] = useState(0);

  useEffect(() => {
    if (lockedFor <= 0) return;
    const timer = window.setTimeout(() => setLockedFor((s) => s - 1), 1000);
    return () => window.clearTimeout(timer);
  }, [lockedFor]);

  const { register, handleSubmit, setError, formState } = useForm<FormInput, unknown, FormOutput>({
    resolver: zodResolver(schema),
    defaultValues: { email: "", password: "" },
    mode: "onTouched",
  });

  const login = useMutation({
    mutationFn: ({ email, password }: FormOutput) => authApi.login(email, password),
    onSuccess: async (result) => {
      await session.setUser(result.user, result.next === "home");
      if (result.next === "onboarding") navigate("/diagnostico", { replace: true });
      else navigate(safeReturnPath(params.get("volver")) ?? "/inicio", { replace: true });
    },
    onError: (error) => {
      if (!isApiError(error)) return;
      if (error.code === "VALIDATION_ERROR") {
        for (const f of error.fields) {
          if (f.field === "email" || f.field === "password") setError(f.field, { type: "server", message: fieldMessage(f.field, f.code) });
        }
      }
      if (error.code === "RATE_LIMITED") setLockedFor(Math.ceil(error.retryAfter ?? 60));
    },
  });

  const error = login.error;
  const submittedEmail = login.variables?.email ?? "";

  return (
    <Page>
      <h1 className="text-3xl font-extrabold">Inicia sesión</h1>
      <p className="mt-2 text-muted">Entra con tu correo institucional.</p>

      <form noValidate onSubmit={handleSubmit((values) => login.mutate(values))} className="mt-8 flex flex-col gap-6">
        <TextField
          label="Correo institucional"
          type="email"
          inputMode="email"
          autoComplete="username"
          spellCheck={false}
          placeholder="nombre.apellido@correounivalle.edu.co"
          error={formState.errors.email?.message}
          {...register("email")}
        />
        <PasswordField
          label="Contraseña"
          autoComplete="current-password"
          error={formState.errors.password?.message}
          {...register("password")}
        />

        <div aria-live="assertive">
          {isApiError(error, "INVALID_CREDENTIALS") && (
            <Banner tone="danger" live="off">El correo o la contraseña no son correctos.</Banner>
          )}
          {isApiError(error, "ACCOUNT_NOT_FOUND") && (
            <Banner tone="info" live="off" actions={<ButtonLink to={`/registro?correo=${encodeURIComponent(submittedEmail)}`}>Crear cuenta</ButtonLink>}>
              {error.message}
            </Banner>
          )}
          {isApiError(error, "EMAIL_NOT_VERIFIED") && (
            <Banner tone="warn" live="off" title={error.message}>
              <div className="mt-2">
                <ResendVerification email={submittedEmail} label="Reenviar enlace de verificación" />
              </div>
            </Banner>
          )}
          {isApiError(error, "RATE_LIMITED") && (
            <Banner tone="danger" live="off">
              Demasiados intentos. Intenta de nuevo {describeWait(lockedFor > 0 ? lockedFor : (error.retryAfter ?? 60))}.
            </Banner>
          )}
          {error && isApiError(error) && !["INVALID_CREDENTIALS", "ACCOUNT_NOT_FOUND", "EMAIL_NOT_VERIFIED", "RATE_LIMITED", "VALIDATION_ERROR"].includes(error.code) && (
            <Banner tone="danger" live="off">{error.message}</Banner>
          )}
        </div>

        <Button type="submit" fullWidth loading={login.isPending} loadingText="Entrando…" disabled={lockedFor > 0}>
          {lockedFor > 0 ? `Espera ${lockedFor} s` : "Iniciar sesión"}
        </Button>
        <p className="text-center">
          ¿No tienes cuenta?{" "}
          <Link to="/registro" className="font-bold text-primary-text underline">
            Regístrate
          </Link>
        </p>
      </form>
    </Page>
  );
}
