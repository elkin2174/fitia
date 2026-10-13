import { screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { TodayPlan } from "../../shared/api/types";
import {
  EXERCISE_DISCLAIMER,
  ME,
  ME_NO_PROFILE,
  planDayDetailFixture,
  todayPlanFixture,
} from "../fixtures";
import { pathOf, renderRoute } from "../render";
import { API, http, ok, sent, server } from "../server";

describe("HU 10 — Rutina de hoy (/hoy)", () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true, now: new Date("2026-10-12T14:00:00Z") });
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it("AC-10-1: día de entrenamiento muestra ejercicios en orden con prescripción y guía accesible", async () => {
    const todayData = todayPlanFixture();
    server.use(http.get(`${API}/plan/today`, () => ok(todayData)));

    const { user } = renderRoute("/hoy", { me: ME });

    expect(await screen.findByRole("heading", { name: "Tu rutina de hoy" })).toBeInTheDocument();
    expect(screen.getByText("Fuerza tren inferior")).toBeInTheDocument();
    expect(screen.getByText("30 min")).toBeInTheDocument();

    // Comprobar ejercicios
    expect(screen.getByText("Sentadilla libre")).toBeInTheDocument();
    expect(screen.getByText("3 series · 12 repeticiones · Descanso 60 s")).toBeInTheDocument();
    expect(screen.getByText("Plancha frontal")).toBeInTheDocument();
    expect(screen.getByText("3 series · 30 s · Descanso 45 s")).toBeInTheDocument();

    // Tocar un ejercicio abre la explicación (HU 13)
    await user.click(screen.getByRole("button", { name: /Sentadilla libre/ }));
    expect(await screen.findByRole("dialog")).toBeInTheDocument();
    expect(screen.getByText("Párate con los pies al ancho de hombros.")).toBeInTheDocument();
    expect(screen.getByText(EXERCISE_DISCLAIMER)).toBeInTheDocument();
  });

  it("AC-10-2: día de descanso muestra aviso y próximo día de entrenamiento con enlace a la rutina", async () => {
    const restData = todayPlanFixture({
      date: "2026-10-13",
      day: planDayDetailFixture({
        date: "2026-10-13",
        weekday: 2,
        status: "rest",
        title: null,
        estimated_minutes: null,
        exercises: [],
      }),
      next_training_day: {
        date: "2026-10-14",
        weekday: 3,
        title: "Fuerza tren superior",
        planned: true,
      },
    });
    server.use(http.get(`${API}/plan/today`, () => ok(restData)));

    const { user, router } = renderRoute("/hoy", { me: ME });

    expect(await screen.findByRole("heading", { name: "Día de descanso" })).toBeInTheDocument();
    expect(screen.getByText("Hoy no tienes entrenamiento programado")).toBeInTheDocument();
    expect(screen.getByText("Fuerza tren superior")).toBeInTheDocument();

    // Enlace a la rutina del próximo día
    const link = screen.getByRole("link", { name: /Ver rutina del 14 de oct/ });
    expect(link).toBeInTheDocument();
    await user.click(link);
    expect(pathOf(router)).toBe("/plan/dia/2026-10-14");
  });

  it("AC-10-2: fin de semana muestra descanso de fin de semana y opción de generar si no tiene plan", async () => {
    const weekendData = todayPlanFixture({
      date: "2026-10-17",
      is_weekend: true,
      plan_status: "none",
      day: null,
      next_training_day: {
        date: "2026-10-19",
        weekday: 1,
        title: null,
        planned: false,
      },
    });
    server.use(http.get(`${API}/plan/today`, () => ok(weekendData)));
    server.use(http.post(`${API}/plan/generate`, () => ok({ plan_id: "p1", status: "generating" }, 202)));

    const { user } = renderRoute("/hoy", { me: ME });

    expect(await screen.findByRole("heading", { name: "Fin de semana de descanso" })).toBeInTheDocument();
    expect(screen.getByText(/lunes 19 de octubre/)).toBeInTheDocument();
    const generateBtn = screen.getByRole("button", { name: "Generar mi plan" });
    expect(generateBtn).toBeInTheDocument();

    await user.click(generateBtn);
    expect(sent("POST", "/plan/generate")).toHaveLength(1);
  });

  it("AC-10-3: estados none, generating y failed", async () => {
    let currentStatus: TodayPlan = todayPlanFixture({ plan_status: "none", day: null });
    server.use(http.get(`${API}/plan/today`, () => ok(currentStatus)));
    server.use(
      http.post(`${API}/plan/generate`, () => {
        currentStatus = todayPlanFixture({ plan_status: "generating", day: null });
        return ok({ plan_id: "p1", status: "generating" }, 202);
      })
    );

    const { user, queryClient } = renderRoute("/hoy", {
      me: ME,
      advanceTimers: vi.advanceTimersByTime,
    });

    expect(await screen.findByText("Aún no tienes plan para esta semana")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Generar mi plan" }));
    expect(sent("POST", "/plan/generate")).toHaveLength(1);

    // Tras generar pasa a generating
    expect(await screen.findByRole("heading", { name: "Estamos armando tu plan…" })).toBeInTheDocument();

    // 3. Estado failed
    currentStatus = todayPlanFixture({
      plan_status: "failed",
      failure: { code: "AI_UNAVAILABLE" },
      day: null,
    });
    await queryClient.invalidateQueries();
    expect(await screen.findByText("El servicio de planes no está disponible ahora.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Reintentar" })).toBeInTheDocument();
  });

  it("AC-10-4: solo lectura, sin botones para editar, agregar ni borrar ejercicios", async () => {
    server.use(http.get(`${API}/plan/today`, () => ok(todayPlanFixture())));

    renderRoute("/hoy", { me: ME });

    await screen.findByRole("heading", { name: "Tu rutina de hoy" });
    expect(screen.queryByRole("button", { name: /editar/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /agregar/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /eliminar/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /reemplazar/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
  });

  it("AC-10-5: visitante sin sesión es redirigido al login", async () => {
    const { router } = renderRoute("/hoy", { me: null });
    await waitFor(() => expect(pathOf(router)).toBe("/iniciar-sesion?volver=%2Fhoy"));
  });

  it("AC-10-5: usuario sin perfil completado es redirigido al diagnóstico", async () => {
    server.use(http.get(`${API}/onboarding/questionnaire`, () => ok({ questions: [] })));
    const { router } = renderRoute("/hoy", { me: ME_NO_PROFILE });
    await waitFor(() => expect(pathOf(router)).toBe("/diagnostico"));
  });
});
