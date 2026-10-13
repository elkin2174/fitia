import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useMemo } from "react";
import { Controller, useForm } from "react-hook-form";
import { Link, useNavigate, useSearchParams } from "react-router";
import { z } from "zod";
import { Page } from "../../app/AppLayout";
import { isApiError, type ApiError } from "../../shared/api/client";
import { fieldMessage } from "../../shared/lib/fieldErrors";
import { describeWait } from "../../shared/lib/retryAfter";
import { Banner } from "../../shared/ui/Banner";
import { Button } from "../../shared/ui/Button";
import { SearchSelect } from "../../shared/ui/SearchSelect";
import { PasswordField, TextField } from "../../shared/ui/TextField";
import { authApi } from "./api";

const DOMAIN = "correounivalle.edu.co";

// Refleja las reglas del backend (HU 1). El backend sigue siendo la fuente de verdad.
const schema = z.object({
  nickname: z
    .string()
    .transform((v) => v.trim())
    .pipe(z.string().min(3, fieldMessage("nickname", "NICKNAME_LENGTH")).max(20, fieldMessage("nickname", "NICKNAME_LENGTH"))),
  email: z
    .string()
    .transform((v) => v.trim().toLowerCase())
    .pipe(
      z
        .string()
        .regex(/^[^@\s]+@[^@\s]+\.[^@\s]+$/, fieldMessage("email", "INVALID_EMAIL"))
        .refine((v) => v.split("@")[1] === DOMAIN, fieldMessage("email", "DOMAIN_NOT_ALLOWED")),
    ),
  password: z.string().min(8, fieldMessage("password", "WEAK_PASSWORD")).max(128, fieldMessage("password", "PASSWORD_TOO_LONG")),
  program_code: z.string({ error: fieldMessage("program_code", "PROGRAM_REQUIRED") }).min(1, fieldMessage("program_code", "PROGRAM_REQUIRED")),
  accepted_terms: z.boolean().refine((v) => v === true, fieldMessage("accepted_terms", "TERMS_REQUIRED")),
});

type FormInput = z.input<typeof schema>;
type FormOutput = z.output<typeof schema>;
type FieldName = keyof FormInput;
const FIELD_NAMES: FieldName[] = ["nickname", "email", "password", "program_code", "accepted_terms"];

export function RegisterPage() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const programs = useQuery({ queryKey: ["programs"], queryFn: authApi.programs, staleTime: Infinity });

  const programItems = useMemo(
    () => (programs.data ?? []).map((p) => ({ value: p.code, label: p.name })),
    [programs.data],
  );

  const form = useForm<FormInput, unknown, FormOutput>({
    resolver: zodResolver(schema),
    defaultValues: { nickname: "", email: params.get("correo") ?? "", password: "", program_code: "", accepted_terms: false },
    mode: "onTouched",
  });
  const { register, handleSubmit, control, watch, setError, formState } = form;
  const { errors } = formState;

  const mutation = useMutation({
    mutationFn: authApi.register,
    onSuccess: (_data, input) => navigate("/registro/revisa-tu-correo", { state: { email: input.email } }),
    onError: (error) => {
      if (!isApiError(error)) return;
      // Muestra a la vez todos los errores de campo que devuelva el backend.
      for (const f of error.fields) {
        if (FIELD_NAMES.includes(f.field as FieldName)) {
          const message = f.code === "DOMAIN_NOT_ALLOWED" && error.message ? error.message : fieldMessage(f.field, f.code);
          setError(f.field as FieldName, { type: "server", message });
        }
      }
    },
  });

  const onSubmit = handleSubmit((values) =>
    mutation.mutate({ ...values, accepted_terms: values.accepted_terms === true }),
  );

  const nickname = watch("nickname") ?? "";
  const password = watch("password") ?? "";
  const serverError = mutation.error as ApiError | null;

  return (
    <Page>
      <h1 className="text-3xl font-extrabold">Crea tu cuenta</h1>
      <p className="mt-2 text-muted">Con tu correo institucional armamos tu plan y te sumamos al ranking de Univalle.</p>

      <form noValidate onSubmit={onSubmit} className="mt-8 flex flex-col gap-6" aria-describedby="register-status">
        <div id="register-status" aria-live="assertive">
          {serverError && isApiError(serverError, "EMAIL_EXISTS") && (
            <Banner tone="warn" title="Este correo ya tiene cuenta." live="off" actions={<Link className="font-bold text-primary-text underline" to="/iniciar-sesion">Iniciar sesión</Link>}>
              Si es tuyo, inicia sesión. Si aún no lo verificas, puedes pedir un enlace nuevo desde el inicio de sesión.
            </Banner>
          )}
          {serverError && isApiError(serverError, "RATE_LIMITED") && (
            <Banner tone="danger" live="off">
              Hiciste varios intentos seguidos. Intenta de nuevo {describeWait(serverError.retryAfter ?? 60)}.
            </Banner>
          )}
          {serverError && !["EMAIL_EXISTS", "RATE_LIMITED", "VALIDATION_ERROR", "DOMAIN_NOT_ALLOWED"].includes(serverError.code) && (
            <Banner tone="danger" live="off">
              {serverError.message}
            </Banner>
          )}
          {serverError?.code === "VALIDATION_ERROR" && (
            <Banner tone="danger" live="off">Revisa los campos marcados.</Banner>
          )}
        </div>

        <TextField
          label="Apodo"
          hint="Así te verán en el ranking. No uses tu nombre completo si prefieres privacidad."
          autoComplete="nickname"
          maxLength={40}
          counter={{ value: nickname.trim().length, max: 20 }}
          error={errors.nickname?.message}
          {...register("nickname")}
        />
        <TextField
          label="Correo institucional"
          type="email"
          inputMode="email"
          autoComplete="email"
          spellCheck={false}
          placeholder="nombre.apellido@correounivalle.edu.co"
          hint="Usa tu correo @correounivalle.edu.co"
          error={errors.email?.message}
          {...register("email")}
        />
        <PasswordField
          label="Contraseña"
          autoComplete="new-password"
          minLength={8}
          valueLength={password.length}
          error={errors.password?.message}
          {...register("password")}
        />
        <Controller
          control={control}
          name="program_code"
          render={({ field }) => (
            <SearchSelect
              label="Programa académico"
              placeholder="Busca tu programa"
              items={programItems}
              value={field.value || null}
              onChange={(value) => field.onChange(value ?? "")}
              loading={programs.isPending}
              error={errors.program_code?.message ?? (programs.isError ? "No pudimos cargar los programas." : undefined)}
            />
          )}
        />
        {programs.isError && (
          <Button variant="ghost" onClick={() => programs.refetch()}>
            Volver a cargar programas
          </Button>
        )}

        <div className="flex flex-col gap-2">
          <label className="flex min-h-11 cursor-pointer items-start gap-3">
            <input
              type="checkbox"
              className="mt-1 size-5 shrink-0 accent-[var(--c-primary)]"
              aria-invalid={errors.accepted_terms ? true : undefined}
              aria-describedby={errors.accepted_terms ? "terms-error" : undefined}
              {...register("accepted_terms")}
            />
            <span>Acepto el tratamiento de mis datos personales para usar FITIA.</span>
          </label>
          <details className="ml-8 text-sm text-muted">
            <summary className="cursor-pointer font-bold text-primary-text">Leer el texto de tratamiento de datos</summary>
            <p className="mt-2">
              Texto provisional: el documento definitivo se publicará con la HU 8. FITIA usa tu correo para identificarte, tu
              apodo y programa para el ranking, y tus respuestas del diagnóstico para armar tu plan. Puedes eliminar tu cuenta
              y tus datos cuando quieras desde tu perfil.
            </p>
          </details>
          {errors.accepted_terms && (
            <p id="terms-error" className="text-sm font-bold text-danger">
              {errors.accepted_terms.message}
            </p>
          )}
        </div>

        <Button type="submit" fullWidth loading={mutation.isPending} loadingText="Creando tu cuenta…">
          Crear mi cuenta
        </Button>
        <p className="text-center">
          ¿Ya tienes cuenta?{" "}
          <Link to="/iniciar-sesion" className="font-bold text-primary-text underline">
            Inicia sesión
          </Link>
        </p>
      </form>
    </Page>
  );
}
