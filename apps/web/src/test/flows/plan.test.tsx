import { act, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { POLL_INTERVAL_MS, SLOW_GENERATION_MS } from "../../features/plan/HomePage";
import { ME, plan } from "../fixtures";
import { renderRoute } from "../render";
import { API, apiError, http, ok, sent, server } from "../server";
import type { CurrentPlan } from "../../shared/api/types";

/** Respuestas sucesivas de GET /plan/current (la última se repite). */
function sequence(...plans: CurrentPlan[]) {
  let i = 0;
  server.use(http.get(`${API}/plan/current`, () => ok(plans[Math.min(i++, plans.length - 1)]!)));
}
const advance = (ms: number) => act(() => vi.advanceTimersByTimeAsync(ms));

describe("HU 5 — plan semanal", () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true, now: new Date("2026-10-12T14:00:00Z") });
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it("sin plan genera automáticamente UNA vez y sondea hasta ready sin bloquear", async () => {
    sequence(plan({ status: "none" }), plan({ status: "generating" }), plan({ status: "generating" }), plan());
    server.use(http.post(`${API}/plan/generate`, () => ok({ plan_id: "p1", status: "generating" }, 202)));
    renderRoute("/inicio", { me: ME, advanceTimers: vi.advanceTimersByTime });

    expect(await screen.findByRole("heading", { name: "Estamos armando tu plan…" })).toBeInTheDocument();
    expect(screen.getByRole("navigation", { name: "Navegación principal" })).toBeInTheDocument(); // la app sigue usable
    await advance(POLL_INTERVAL_MS);
    await advance(POLL_INTERVAL_MS);
    expect(await screen.findByRole("list", { name: "Tu semana de lunes a viernes" })).toBeInTheDocument();
    expect(screen.getByText("Rutina del día 1")).toBeInTheDocument();
    expect(screen.getAllByText("Descanso")).toHaveLength(2);
    expect(sent("POST", "/plan/generate")).toHaveLength(1);

    const gets = sent("GET", "/plan/current").length;
    await advance(POLL_INTERVAL_MS * 3);
    expect(sent("GET", "/plan/current")).toHaveLength(gets); // con el plan listo deja de sondear
  });

  it("failed NO reintenta solo; Reintentar hace el POST", async () => {
    sequence(plan({ status: "failed", failure: { code: "AI_UNAVAILABLE" } }), plan({ status: "generating" }));
    server.use(http.post(`${API}/plan/generate`, () => ok({ plan_id: "p2", status: "generating" }, 202)));
    const { user } = renderRoute("/inicio", { me: ME, advanceTimers: vi.advanceTimersByTime });

    expect(await screen.findByText("El servicio de planes no está disponible ahora.")).toBeInTheDocument();
    await advance(POLL_INTERVAL_MS * 4);
    expect(sent("POST", "/plan/generate")).toHaveLength(0);

    await user.click(screen.getByRole("button", { name: "Reintentar" }));
    expect(await screen.findByRole("heading", { name: "Estamos armando tu plan…" })).toBeInTheDocument();
    expect(sent("POST", "/plan/generate")).toHaveLength(1);
  });

  it("a los 60 s ofrece seguir esperando o reintentar", async () => {
    sequence(plan({ status: "generating" }));
    renderRoute("/inicio", { me: ME, advanceTimers: vi.advanceTimersByTime });
    await screen.findByRole("heading", { name: "Estamos armando tu plan…" });
    expect(screen.queryByText("Está tardando más de lo normal.")).not.toBeInTheDocument();

    await advance(SLOW_GENERATION_MS);
    expect(await screen.findByText("Está tardando más de lo normal.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Seguir esperando" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Reintentar" })).toBeInTheDocument();
  });

  it("plan vigente con fallo de actualización: muestra la semana y el aviso", async () => {
    sequence(plan({ failure: { code: "GENERATION_TIMEOUT" }, outdated: true, can_regenerate: true }));
    renderRoute("/inicio", { me: ME });
    expect(await screen.findByText("No pudimos actualizar tu plan.")).toBeInTheDocument();
    expect(screen.getByText(/La generación tardó más de lo esperado/)).toBeInTheDocument();
    expect(screen.getByRole("list", { name: "Tu semana de lunes a viernes" })).toBeInTheDocument();
  });

  it("desactualizado sin cupo explica el límite y no ofrece actualizar", async () => {
    sequence(plan({ outdated: true, can_regenerate: false }));
    renderRoute("/inicio", { me: ME });
    expect(await screen.findByText(/Ya usaste las actualizaciones de esta semana/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Actualizar mi plan" })).not.toBeInTheDocument();
  });

  it("actualizar con 429 REGENERATION_LIMIT dice cuándo podrá generar", async () => {
    sequence(plan({ outdated: true, can_regenerate: true }));
    server.use(http.post(`${API}/plan/generate`, () => apiError(429, "REGENERATION_LIMIT", "x", [], { "Retry-After": String(6 * 86400 + 15 * 3600) })));
    const { user } = renderRoute("/inicio", { me: ME, advanceTimers: vi.advanceTimersByTime });
    await user.click(await screen.findByRole("button", { name: "Actualizar mi plan" }));
    expect(await screen.findByText(/podrás generar uno nuevo el lunes 19 de octubre/)).toBeInTheDocument();
  });

  it("regenerando: el plan vigente sigue visible con un aviso", async () => {
    sequence(plan({ regenerating: true }));
    renderRoute("/inicio", { me: ME });
    expect(await screen.findByText("Estamos actualizando tu plan…")).toBeInTheDocument();
    expect(screen.getByRole("list", { name: "Tu semana de lunes a viernes" })).toBeInTheDocument();
  });

  it("plan vacío explica que no quedan días esta semana", async () => {
    const empty = plan();
    sequence({ ...empty, days: empty.days.map((d) => ({ ...d, status: d.weekday < 5 ? "unplanned" : "rest", title: null, estimated_minutes: null })) });
    renderRoute("/inicio", { me: ME });
    expect(await screen.findByText("No quedan días de entrenamiento esta semana")).toBeInTheDocument();
  });

  it("el fin de semana indica que el plan es de la semana siguiente", async () => {
    sequence(plan({ week_start: "2026-10-19", start_date: "2026-10-19" }));
    vi.setSystemTime(new Date("2026-10-17T15:00:00Z")); // sábado
    renderRoute("/inicio", { me: ME });
    expect(await screen.findByRole("heading", { name: "Tu plan para la semana del 19 de octubre" })).toBeInTheDocument();
  });

  it("nunca ofrece acciones para editar el plan", async () => {
    sequence(plan());
    renderRoute("/inicio", { me: ME });
    await screen.findByRole("list", { name: "Tu semana de lunes a viernes" });
    expect(screen.queryByRole("button", { name: /editar|borrar|eliminar|reordenar/i })).not.toBeInTheDocument();
  });
});
