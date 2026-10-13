import { screen, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ME_NO_PROFILE, QUESTIONNAIRE, plan } from "../fixtures";
import { pathOf, renderRoute } from "../render";
import { API, apiError, http, ok, sent, server } from "../server";

async function answerAll(user: ReturnType<typeof renderRoute>["user"]) {
  const choose = async (label: string) => {
    await user.click(await screen.findByRole("radio", { name: label }));
    await user.click(screen.getByRole("button", { name: /Siguiente|Ver resumen/ }));
  };
  await choose("Fuerza");
  await choose("8 semanas");
  await choose("Principiante");
  await choose("30 min");
  await choose("No");
  await user.click(await screen.findByRole("checkbox", { name: "Lunes" }));
  await user.click(screen.getByRole("checkbox", { name: "Miércoles" }));
  await user.click(screen.getByRole("button", { name: "Ver resumen" }));
}

describe("HU 4 — diagnóstico inicial", () => {
  it("se arma solo con el cuestionario y envía cada code con su tipo JSON", async () => {
    server.use(
      http.get(`${API}/onboarding/questionnaire`, () => ok(QUESTIONNAIRE)),
      http.post(`${API}/onboarding/complete`, () => ok({ profile: {} }, 201)),
      http.post(`${API}/plan/generate`, () => ok({ plan_id: "p1", status: "generating" }, 202)),
      http.get(`${API}/plan/current`, () => ok(plan({ status: "generating" }))),
    );
    const { user, router } = renderRoute("/diagnostico", { me: ME_NO_PROFILE });
    expect(await screen.findByText("Hola, Pantera.")).toBeInTheDocument();
    expect(screen.getByText("Pregunta 1 de 6")).toBeInTheDocument();
    await answerAll(user);
    expect(await screen.findByText("Revisa tus respuestas")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Confirmar y armar mi plan" }));

    await waitFor(() => expect(pathOf(router)).toBe("/inicio"));
    const body = sent("POST", "/onboarding/complete")[0]?.body as Record<string, unknown>;
    expect(body).toEqual({
      goal: "strength",
      term_weeks: 8,
      fitness_level: "beginner",
      session_minutes: 30,
      has_machine_access: false,
      training_days: [1, 3],
    });
    expect(typeof body.term_weeks).toBe("number");
    expect(typeof body.has_machine_access).toBe("boolean");
    expect(sent("POST", "/plan/generate")).toHaveLength(1);
  });

  it("no deja avanzar sin responder ni sin elegir días", async () => {
    server.use(http.get(`${API}/onboarding/questionnaire`, () => ok(QUESTIONNAIRE)));
    const { user } = renderRoute("/diagnostico", { me: ME_NO_PROFILE });
    await user.click(await screen.findByRole("button", { name: "Siguiente" }));
    expect(screen.getByText("Elige una opción para continuar.")).toBeInTheDocument();
    expect(screen.getByText("Pregunta 1 de 6")).toBeInTheDocument();
  });

  it("422 lleva a la primera pregunta marcada", async () => {
    server.use(
      http.get(`${API}/onboarding/questionnaire`, () => ok(QUESTIONNAIRE)),
      http.post(`${API}/onboarding/complete`, () =>
        apiError(422, "VALIDATION_ERROR", "Hay respuestas que no corresponden a las opciones disponibles.", [
          { field: "session_minutes", code: "INVALID_OPTION" },
        ]),
      ),
    );
    const { user } = renderRoute("/diagnostico", { me: ME_NO_PROFILE });
    await answerAll(user);
    await user.click(await screen.findByRole("button", { name: "Confirmar y armar mi plan" }));
    expect(await screen.findByText("Pregunta 4 de 6")).toBeInTheDocument();
    expect(screen.getByText("Elige una de las opciones disponibles.")).toBeInTheDocument();
  });

  it("409 PROFILE_EXISTS se trata como ya completado", async () => {
    server.use(
      http.get(`${API}/onboarding/questionnaire`, () => ok(QUESTIONNAIRE)),
      http.post(`${API}/onboarding/complete`, () => apiError(409, "PROFILE_EXISTS", "Ya completaste tu diagnóstico.")),
      http.get(`${API}/plan/current`, () => ok(plan())),
    );
    const { user, router } = renderRoute("/diagnostico", { me: ME_NO_PROFILE });
    await answerAll(user);
    await user.click(await screen.findByRole("button", { name: "Confirmar y armar mi plan" }));
    await waitFor(() => expect(pathOf(router)).toBe("/inicio"));
  });
});
