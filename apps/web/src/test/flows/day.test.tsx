import { screen, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import {
  ME,
  ME_NO_PROFILE,
  plan,
  planDayDetailFixture,
} from "../fixtures";
import { pathOf, renderRoute } from "../render";
import { API, apiError, http, ok, server } from "../server";

describe("HU 12 — Calendario semanal y detalle del día (/plan/dia/:fecha)", () => {
  it("AC-12-1: en /inicio los días de entrenamiento son enlaces a /plan/dia/:fecha y descanso no enlaza", async () => {
    server.use(http.get(`${API}/plan/current`, () => ok(plan())));

    const { user, router } = renderRoute("/inicio", { me: ME });

    // Días de entrenamiento son enlaces
    const trainingLink = await screen.findByRole("link", { name: /lunes 12 de octubre.*ver rutina/i });
    expect(trainingLink).toBeInTheDocument();

    // Días de descanso no son enlaces
    expect(
      screen.queryByRole("link", { name: /martes 13 de octubre.*ver rutina/i })
    ).not.toBeInTheDocument();

    // Al hacer clic navega al detalle del día (AC-12-2)
    server.use(http.get(`${API}/plan/days/2026-10-12`, () => ok(planDayDetailFixture())));
    await user.click(trainingLink);
    expect(pathOf(router)).toBe("/plan/dia/2026-10-12");
  });

  it("AC-12-2: detalle de día de entrenamiento muestra rutina completa, solo lectura", async () => {
    const dayData = planDayDetailFixture({
      date: "2026-10-12",
      weekday: 1,
      status: "training",
      title: "Fuerza tren inferior",
      estimated_minutes: 30,
    });
    server.use(http.get(`${API}/plan/days/2026-10-12`, () => ok(dayData)));

    const { user, router } = renderRoute("/plan/dia/2026-10-12", { me: ME });

    expect(await screen.findByRole("heading", { name: "Fuerza tren inferior" })).toBeInTheDocument();
    expect(screen.getByText("30 min")).toBeInTheDocument();
    expect(screen.getByText("Sentadilla libre")).toBeInTheDocument();
    expect(screen.getByText("Plancha frontal")).toBeInTheDocument();

    // Sin controles de edición
    expect(screen.queryByRole("button", { name: /editar/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /agregar/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /eliminar/i })).not.toBeInTheDocument();

    // Enlace para volver a la semana
    const backLink = screen.getByRole("link", { name: /Volver a la semana/ });
    expect(backLink).toBeInTheDocument();
    server.use(http.get(`${API}/plan/current`, () => ok(plan())));
    await user.click(backLink);
    expect(pathOf(router)).toBe("/inicio");
  });

  it("AC-12-3: día de descanso se muestra como descanso y sin ejercicios", async () => {
    const restDay = planDayDetailFixture({
      date: "2026-10-13",
      weekday: 2,
      status: "rest",
      title: null,
      estimated_minutes: null,
      exercises: [],
    });
    server.use(http.get(`${API}/plan/days/2026-10-13`, () => ok(restDay)));

    renderRoute("/plan/dia/2026-10-13", { me: ME });

    expect(await screen.findByRole("heading", { name: "Día de descanso" })).toBeInTheDocument();
    expect(
      screen.getByText("Este día no tiene ejercicios programados. Aprovecha para descansar y recuperarte.")
    ).toBeInTheDocument();
    expect(screen.queryByText("Sentadilla libre")).not.toBeInTheDocument();
  });

  it("AC-12-4: error al cargar día muestra mensaje y botón reintentar", async () => {
    server.use(
      http.get(`${API}/plan/days/2026-10-12`, () =>
        apiError(404, "PLAN_DAY_NOT_FOUND", "El día solicitado no forma parte de tu plan semanal.")
      )
    );

    renderRoute("/plan/dia/2026-10-12", { me: ME });

    expect(
      await screen.findByText("El día solicitado no forma parte de tu plan semanal.")
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Reintentar" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Volver a la semana/ })).toBeInTheDocument();
  });

  it("seguridad: sin sesión redirige al login guardando la ruta", async () => {
    const { router } = renderRoute("/plan/dia/2026-10-12", { me: null });
    await waitFor(() => expect(pathOf(router)).toBe("/iniciar-sesion?volver=%2Fplan%2Fdia%2F2026-10-12"));
  });

  it("seguridad: usuario sin perfil completado redirige al diagnóstico", async () => {
    server.use(http.get(`${API}/onboarding/questionnaire`, () => ok({ questions: [] })));
    const { router } = renderRoute("/plan/dia/2026-10-12", { me: ME_NO_PROFILE });
    await waitFor(() => expect(pathOf(router)).toBe("/diagnostico"));
  });
});
