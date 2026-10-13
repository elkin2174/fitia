import { screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ME, PROFILE, QUESTIONNAIRE, plan } from "../fixtures";
import { pathOf, renderRoute } from "../render";
import { API, apiError, http, ok, sent, server } from "../server";

const MESSAGE =
  "Tu diagnóstico se actualizó correctamente. Los cambios se aplicarán al próximo plan que generes. Tu plan actual no ha cambiado.";

function profileApi(profile = PROFILE) {
  server.use(
    http.get(`${API}/profile`, () => ok({ profile })),
    http.get(`${API}/onboarding/questionnaire`, () => ok(QUESTIONNAIRE)),
  );
}

describe("HU 6 y HU 7 — perfil", () => {
  it("muestra el diagnóstico con las etiquetas del cuestionario y el estado inicial de puntos", async () => {
    profileApi();
    renderRoute("/perfil", { me: ME });
    expect(await screen.findByText("Fuerza")).toBeInTheDocument();
    expect(screen.getByText("Lunes, Miércoles, Viernes")).toBeInTheDocument();
    expect(screen.getByText(/Completa entrenamientos para sumar puntos/)).toBeInTheDocument();
    expect(screen.getByText("Aún no has registrado tu peso ni tu estatura.")).toBeInTheDocument();
  });

  it("guardar envía SOLO el campo que cambió y muestra el mensaje de la API", async () => {
    profileApi();
    server.use(http.patch(`${API}/profile`, () => ok({ profile: { ...PROFILE, goal: "endurance" }, message: MESSAGE })));
    const { user } = renderRoute("/perfil", { me: ME });
    await user.click(await screen.findByRole("button", { name: "Editar" }));
    expect(screen.getByText(/Tu plan actual no cambia/)).toBeInTheDocument();
    await user.click(screen.getByRole("radio", { name: "Resistencia" }));
    await user.click(screen.getByRole("button", { name: "Guardar diagnóstico" }));

    expect(await screen.findByText(MESSAGE)).toBeInTheDocument();
    const [patch] = sent("PATCH", "/profile");
    expect(patch?.body).toEqual({ goal: "endurance" });
    expect(patch?.headers["x-requested-with"]).toBe("fitia");
    expect(screen.getByRole("link", { name: "Ir a mi plan" })).toHaveAttribute("href", "/inicio");
  });

  it("sin cambios no envía la petición", async () => {
    profileApi();
    const { user } = renderRoute("/perfil", { me: ME });
    await user.click(await screen.findByRole("button", { name: "Editar" }));
    await user.click(screen.getByRole("button", { name: "Guardar diagnóstico" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "Editar" })).toBeInTheDocument());
    expect(sent("PATCH", "/profile")).toHaveLength(0);
  });

  it("cancelar con cambios pide confirmación y, al descartar, vuelve a lo guardado sin peticiones", async () => {
    profileApi();
    const { user } = renderRoute("/perfil", { me: ME });
    await user.click(await screen.findByRole("button", { name: "Editar" }));
    await user.click(screen.getByRole("radio", { name: "Resistencia" }));
    await user.click(screen.getByRole("button", { name: "Cancelar" }));

    const dialog = await screen.findByRole("dialog", { name: "¿Descartar los cambios?" });
    await user.click(within(dialog).getByRole("button", { name: "Descartar cambios" }));
    expect(await screen.findByText("Fuerza")).toBeInTheDocument();
    expect(sent("PATCH", "/profile")).toHaveLength(0);
  });

  it("si el guardado falla, conserva lo escrito y lo guardado no cambia", async () => {
    profileApi();
    server.use(http.patch(`${API}/profile`, () => apiError(500, "INTERNAL_ERROR", "Ocurrió un error inesperado.")));
    const { user } = renderRoute("/perfil", { me: ME });
    await user.click(await screen.findByRole("button", { name: "Editar" }));
    await user.click(screen.getByRole("radio", { name: "Resistencia" }));
    await user.click(screen.getByRole("button", { name: "Guardar diagnóstico" }));

    expect(await screen.findByText("Ocurrió un error inesperado.")).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: "Resistencia" })).toHaveAttribute("aria-checked", "true");
  });

  it("salir de la página con cambios sin guardar pide confirmación", async () => {
    profileApi();
    server.use(http.get(`${API}/plan/current`, () => ok(plan())));
    const { user, router } = renderRoute("/perfil", { me: ME });
    await user.click(await screen.findByRole("button", { name: "Editar" }));
    await user.click(screen.getByRole("radio", { name: "Resistencia" }));
    await user.click(screen.getByRole("link", { name: "Inicio" }));

    const dialog = await screen.findByRole("dialog", { name: "¿Descartar los cambios?" });
    await user.click(within(dialog).getByRole("button", { name: "Seguir editando" }));
    expect(pathOf(router)).toBe("/perfil");
    await user.click(screen.getByRole("link", { name: "Inicio" }));
    await user.click(within(await screen.findByRole("dialog")).getByRole("button", { name: "Salir sin guardar" }));
    await waitFor(() => expect(pathOf(router)).toBe("/inicio"));
  });

  it("datos físicos: rango propio en cliente, decimales con coma y mensaje propio al guardar", async () => {
    profileApi();
    server.use(
      http.patch(`${API}/profile`, () =>
        ok({ profile: { ...PROFILE, weight_kg: 68.5, height_cm: 172, physical_updated_at: "2026-10-12T15:00:00Z" }, message: MESSAGE }),
      ),
    );
    const { user } = renderRoute("/perfil", { me: ME });
    await user.click(await screen.findByRole("button", { name: "Agregar mis datos" }));
    await user.type(screen.getByLabelText("Peso (kg)"), "500");
    await user.click(screen.getByRole("button", { name: "Guardar datos físicos" }));
    expect(screen.getByText("El peso debe estar entre 20 y 400 kg.")).toBeInTheDocument();
    expect(sent("PATCH", "/profile")).toHaveLength(0);

    await user.clear(screen.getByLabelText("Peso (kg)"));
    await user.type(screen.getByLabelText("Peso (kg)"), "68,5");
    await user.type(screen.getByLabelText("Estatura (cm)"), "172");
    await user.click(screen.getByRole("button", { name: "Guardar datos físicos" }));

    expect(await screen.findByText("Tus datos físicos se guardaron.")).toBeInTheDocument();
    expect(screen.queryByText(MESSAGE)).not.toBeInTheDocument(); // el mensaje de la API habla del diagnóstico
    expect(sent("PATCH", "/profile")[0]?.body).toEqual({ weight_kg: 68.5, height_cm: 172 });
    expect(screen.getByText("Actualizado el 12 de octubre de 2026")).toBeInTheDocument();
  });

  it("INVALID_OPTION del backend en peso usa el texto con el rango", async () => {
    profileApi({ ...PROFILE, weight_kg: 70, height_cm: 170 });
    server.use(
      http.patch(`${API}/profile`, () =>
        apiError(422, "VALIDATION_ERROR", "Hay respuestas que no corresponden a las opciones disponibles.", [
          { field: "height_cm", code: "INVALID_OPTION" },
        ]),
      ),
    );
    const { user } = renderRoute("/perfil", { me: ME });
    const physical = (await screen.findByRole("heading", { name: "Datos físicos" })).closest("section")!;
    await user.click(within(physical).getByRole("button", { name: "Editar" }));
    await user.clear(screen.getByLabelText("Estatura (cm)"));
    await user.type(screen.getByLabelText("Estatura (cm)"), "180");
    await user.click(screen.getByRole("button", { name: "Guardar datos físicos" }));
    expect(await screen.findByText("La estatura debe estar entre 50 y 270 cm.")).toBeInTheDocument();
    expect(screen.getByLabelText("Estatura (cm)")).toHaveValue("180");
  });
});

describe("HU 7 — privacidad", () => {
  it("el interruptor guarda al instante solo is_public_ranking", async () => {
    profileApi();
    server.use(http.patch(`${API}/profile`, () => ok({ profile: { ...PROFILE, is_public_ranking: false }, message: MESSAGE })));
    const { user } = renderRoute("/perfil", { me: ME });
    const toggle = await screen.findByRole("switch", { name: "Aparecer en el ranking público" });
    expect(toggle).toHaveAttribute("aria-checked", "true");
    await user.click(toggle);

    expect(await screen.findByText("Ya no apareces en el ranking público.")).toBeInTheDocument();
    expect(toggle).toHaveAttribute("aria-checked", "false");
    expect(sent("PATCH", "/profile")[0]?.body).toEqual({ is_public_ranking: false });
  });

  it("si falla, revierte el interruptor y avisa", async () => {
    profileApi();
    server.use(http.patch(`${API}/profile`, () => apiError(500, "INTERNAL_ERROR", "x")));
    const { user } = renderRoute("/perfil", { me: ME });
    const toggle = await screen.findByRole("switch", { name: "Aparecer en el ranking público" });
    await user.click(toggle);

    expect(await screen.findByText("No pudimos cambiar tu privacidad. Intenta de nuevo.")).toBeInTheDocument();
    await waitFor(() => expect(toggle).toHaveAttribute("aria-checked", "true"));
  });
});
