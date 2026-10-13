import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import {
  EXERCISE_DISCLAIMER,
  ME,
  exerciseFixture,
  planDayDetailFixture,
  todayPlanFixture,
} from "../fixtures";
import { pathOf, renderRoute } from "../render";
import { API, http, ok, server } from "../server";

describe("HU 13 — Explicación de ejercicios (bottom sheet)", () => {
  it("AC-13-1 / AC-13-2 / AC-13-4: abre explicación sin cambiar de ruta ni llamar a la IA", async () => {
    const exercise = exerciseFixture({
      id: "e1111111-1111-1111-1111-111111111111",
      name: "Press banca con mancuernas",
      guide: {
        steps: [
          "Acuéstate boca arriba en el banco con una mancuerna en cada mano.",
          "Empuja las mancuernas hacia arriba con los brazos extendidos.",
          "Baja lentamente controlando el peso hasta el nivel del pecho.",
        ],
        disclaimer: EXERCISE_DISCLAIMER,
      },
    });
    const todayData = todayPlanFixture({
      day: planDayDetailFixture({ exercises: [exercise] }),
    });
    server.use(http.get(`${API}/plan/today`, () => ok(todayData)));

    const { user, router } = renderRoute("/hoy", { me: ME });

    // Ver ejercicio en la rutina
    const exerciseBtn = await screen.findByRole("button", { name: /Press banca con mancuernas/ });
    expect(exerciseBtn).toBeInTheDocument();

    // Tocar el ejercicio abre la hoja inferior (AC-13-1)
    await user.click(exerciseBtn);

    // Refleja en el search param ?ejercicio=<id>
    expect(pathOf(router)).toBe(`/hoy?ejercicio=${exercise.id}`);

    // Modal abierto con role="dialog" y aria-modal="true"
    const dialog = screen.getByRole("dialog");
    expect(dialog).toBeInTheDocument();
    expect(dialog).toHaveAttribute("aria-modal", "true");

    // AC-13-2: contenido de pasos y aviso orientativo
    expect(screen.getByText("Acuéstate boca arriba en el banco con una mancuerna en cada mano.")).toBeInTheDocument();
    expect(screen.getByText("Empuja las mancuernas hacia arriba con los brazos extendidos.")).toBeInTheDocument();
    expect(screen.getByText("Baja lentamente controlando el peso hasta el nivel del pecho.")).toBeInTheDocument();
    expect(screen.getByText(EXERCISE_DISCLAIMER)).toBeInTheDocument();
  });

  it("AC-13-3: cerrar con botón X cierra la hoja y remueve el search param", async () => {
    const exercise = exerciseFixture();
    server.use(
      http.get(
        `${API}/plan/today`,
        () => ok(todayPlanFixture({ day: planDayDetailFixture({ exercises: [exercise] }) }))
      )
    );

    const { user, router } = renderRoute(`/hoy?ejercicio=${exercise.id}`, { me: ME });

    // Abre automáticamente por el parámetro de URL
    expect(await screen.findByRole("dialog")).toBeInTheDocument();

    // Cerrar con el botón cerrar
    const closeBtn = screen.getByRole("button", { name: "Cerrar explicación" });
    await user.click(closeBtn);

    // Cierra el diálogo y limpia la URL
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(pathOf(router)).toBe("/hoy");
    // La rutina sigue visible
    expect(screen.getByText(exercise.name)).toBeInTheDocument();
  });

  it("AC-13-3: cerrar con tecla Escape cierra la hoja", async () => {
    const exercise = exerciseFixture();
    server.use(
      http.get(
        `${API}/plan/today`,
        () => ok(todayPlanFixture({ day: planDayDetailFixture({ exercises: [exercise] }) }))
      )
    );

    const { user, router } = renderRoute(`/hoy?ejercicio=${exercise.id}`, { me: ME });

    expect(await screen.findByRole("dialog")).toBeInTheDocument();

    // Presionar tecla Escape
    await user.keyboard("{Escape}");

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(pathOf(router)).toBe("/hoy");
  });

  it("funciona igualmente en la pantalla de detalle del día (/plan/dia/:fecha)", async () => {
    const exercise = exerciseFixture();
    server.use(
      http.get(
        `${API}/plan/days/2026-10-12`,
        () => ok(planDayDetailFixture({ exercises: [exercise] }))
      )
    );

    const { user, router } = renderRoute("/plan/dia/2026-10-12", { me: ME });

    const exButton = await screen.findByRole("button", { name: /Sentadilla libre/ });
    await user.click(exButton);

    expect(pathOf(router)).toBe(`/plan/dia/2026-10-12?ejercicio=${exercise.id}`);
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(screen.getByText(EXERCISE_DISCLAIMER)).toBeInTheDocument();
  });
});
