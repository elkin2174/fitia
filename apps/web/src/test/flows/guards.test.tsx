import { screen, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ME, ME_NO_PROFILE } from "../fixtures";
import { pathOf, renderRoute } from "../render";
import { API, apiError, http, ok, server } from "../server";

describe("guards de ruta y sesión", () => {
  it("sin sesión, una ruta S+P lleva al login guardando la ruta de retorno", async () => {
    const { router } = renderRoute("/perfil");
    await waitFor(() => expect(pathOf(router)).toBe("/iniciar-sesion?volver=%2Fperfil"));
  });

  it("con sesión sin diagnóstico, una ruta S+P lleva a /diagnostico", async () => {
    server.use(http.get(`${API}/onboarding/questionnaire`, () => ok({ questions: [] })));
    const { router } = renderRoute("/inicio", { me: ME_NO_PROFILE });
    await waitFor(() => expect(pathOf(router)).toBe("/diagnostico"));
  });

  it("con sesión, login y registro redirigen a donde corresponde", async () => {
    server.use(http.get(`${API}/plan/current`, () => apiError(500, "INTERNAL_ERROR", "x")));
    const { router } = renderRoute("/registro", { me: ME });
    await waitFor(() => expect(pathOf(router)).toBe("/inicio"));
  });

  it("un 401 UNAUTHENTICATED en una ruta protegida limpia la sesión y lleva al login", async () => {
    server.use(http.get(`${API}/plan/current`, () => apiError(401, "UNAUTHENTICATED", "Debes iniciar sesión.")));
    const { router } = renderRoute("/inicio", { me: ME });
    await waitFor(() => expect(pathOf(router)).toBe("/iniciar-sesion?volver=%2Finicio"));
    expect(await screen.findByRole("heading", { name: "Inicia sesión" })).toBeInTheDocument();
  });

  it("un 403 ONBOARDING_REQUIRED lleva al diagnóstico", async () => {
    server.use(
      http.get(`${API}/profile`, () => apiError(403, "ONBOARDING_REQUIRED", "Completa tu diagnóstico.")),
      http.get(`${API}/onboarding/questionnaire`, () => ok({ questions: [] })),
    );
    const { router } = renderRoute("/perfil", { me: ME });
    await waitFor(() => expect(pathOf(router)).toBe("/diagnostico"));
  });
});
