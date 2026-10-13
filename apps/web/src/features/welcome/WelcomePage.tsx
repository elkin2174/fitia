import { useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";
import { useLocation } from "react-router";
import { Page } from "../../app/AppLayout";
import { forgetSessionEnd, useMe } from "../../shared/session/session";
import { Banner } from "../../shared/ui/Banner";
import { ButtonLink } from "../../shared/ui/Button";
import { WEEKDAY_SHORT } from "../../shared/lib/dates";

const NOTICES: Record<string, { tone: "success" | "info"; text: string }> = {
  account_deleted: {
    tone: "info",
    text: "Tu cuenta y tus datos se eliminaron. Gracias por entrenar con FITIA; si vuelves, puedes registrarte con el mismo correo.",
  },
  logged_out: { tone: "success", text: "Cerraste sesión." },
};

/** Muestra de los carriles de la semana: lo que el estudiante obtiene. */
const PREVIEW = [
  { day: 1, label: "Fuerza de cuerpo completo", minutes: 30 },
  { day: 2, label: "Descanso" },
  { day: 3, label: "Piernas y core", minutes: 30 },
  { day: 4, label: "Descanso" },
  { day: 5, label: "Circuito activo", minutes: 25 },
];

export function WelcomePage() {
  const me = useMe();
  const client = useQueryClient();
  // El aviso de cierre ya se mostró aquí: un acceso posterior a una ruta protegida vuelve a ir al login.
  useEffect(() => forgetSessionEnd(client), [client]);
  const notice = (useLocation().state as { notice?: string } | null)?.notice;
  const message = notice ? NOTICES[notice] : undefined;

  return (
    <Page>
      {message && (
        <Banner tone={message.tone} className="mb-6">
          {message.text}
        </Banner>
      )}
      <h1 className="text-[2.6rem] font-extrabold leading-[1.05] sm:text-5xl">Tu semana de entrenamiento, lista entre clases.</h1>
      <p className="mt-4 text-lg text-muted">
        Responde 6 preguntas y FITIA arma tu plan según tu tiempo, tu nivel y si tienes acceso al gimnasio. Sin planear rutinas
        tú solo.
      </p>

      <div className="mt-7 flex flex-col gap-3 sm:flex-row">
        {me.data ? (
          <ButtonLink to={me.data.onboarding_completed ? "/inicio" : "/diagnostico"} fullWidth>
            Ir a mi plan
          </ButtonLink>
        ) : (
          <>
            <ButtonLink to="/registro" fullWidth>
              Crear mi cuenta
            </ButtonLink>
            <ButtonLink to="/iniciar-sesion" variant="secondary" fullWidth>
              Ya tengo cuenta
            </ButtonLink>
          </>
        )}
      </div>

      <figure className="mt-10" aria-label="Ejemplo de una semana en FITIA">
        <ol className="flex flex-col gap-2" aria-hidden="true">
          {PREVIEW.map((row) => (
            <li key={row.day} className="flex min-h-14 overflow-hidden rounded-[var(--radius-control)] border-2 border-line bg-surface">
              <span
                className={
                  row.day === 1
                    ? "lane-stripes flex w-12 items-center justify-center bg-primary font-display text-xl font-extrabold text-on-primary"
                    : row.minutes
                      ? "flex w-12 items-center justify-center bg-surface-2 font-display text-xl font-extrabold text-muted"
                      : "flex w-12 items-center justify-center bg-rest-soft font-display text-xl font-extrabold text-rest"
                }
              >
                {WEEKDAY_SHORT[row.day]}
              </span>
              <span className="flex flex-1 items-center justify-between gap-3 px-4">
                <span className={row.minutes ? "font-bold" : "font-bold text-rest"}>{row.label}</span>
                {row.minutes && <span className="shrink-0 whitespace-nowrap text-sm text-muted">{row.minutes} min</span>}
              </span>
            </li>
          ))}
        </ol>
        <figcaption className="mt-3 text-sm text-muted">Así se ve una semana: rutinas en tus días libres, descanso en los demás.</figcaption>
      </figure>

      <section className="mt-10" aria-labelledby="how-title">
        <h2 id="how-title" className="text-2xl font-bold">
          Cómo funciona
        </h2>
        <ol className="mt-4 flex flex-col gap-4">
          {[
            ["Crea tu cuenta", "Con tu correo @correounivalle.edu.co y un apodo para el ranking."],
            ["Responde el diagnóstico", "Tu objetivo, tu nivel, tus minutos libres y tus días disponibles."],
            ["Recibe tu plan", "Una rutina para cada día que elegiste, con la explicación de cada ejercicio."],
          ].map(([title, text], i) => (
            <li key={title} className="flex gap-4">
              <span className="grid size-9 shrink-0 place-items-center rounded-full border-2 border-primary font-display font-extrabold text-primary-text">
                {i + 1}
              </span>
              <div>
                <p className="font-bold">{title}</p>
                <p className="text-muted">{text}</p>
              </div>
            </li>
          ))}
        </ol>
      </section>
    </Page>
  );
}
