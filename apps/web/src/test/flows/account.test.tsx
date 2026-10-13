import { screen, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ME, PROFILE, QUESTIONNAIRE } from "../fixtures";
import { pathOf, renderRoute } from "../render";
import { API, apiError, http, HttpResponse, ok, sent, server } from "../server";

describe("HU 3 — eliminar cuenta y cerrar sesión", () => {
  it("cancelar no envía ninguna petición", async () => {
    server.use(
      http.get(`${API}/profile`, () => ok({ profile: PROFILE })),
      http.get(`${API}/onboarding/questionnaire`, () => ok(QUESTIONNAIRE)),
    );
    const { user, router } = renderRoute("/perfil/eliminar-cuenta", { me: ME });
    await user.click(await screen.findByRole("button", { name: "Cancelar" }));
    await waitFor(() => expect(pathOf(router)).toBe("/perfil"));
    expect(sent("POST", "/me/delete-account")).toHaveLength(0);
  });

  it("exige la confirmación activa y envía { confirm: true }", async () => {
    server.use(http.post(`${API}/me/delete-account`, () => new HttpResponse(null, { status: 204 })));
    const { user, router } = renderRoute("/perfil/eliminar-cuenta", { me: ME });
    const remove = await screen.findByRole("button", { name: "Eliminar mi cuenta" });
    expect(remove).toBeDisabled();
    expect(screen.getByText(/Se borran tu perfil, tu diagnóstico, tu plan/)).toBeInTheDocument();

    await user.click(screen.getByRole("checkbox", { name: "Entiendo que es definitivo." }));
    await user.click(remove);

    await waitFor(() => expect(pathOf(router)).toBe("/"));
    const [request] = sent("POST", "/me/delete-account");
    expect(request?.body).toEqual({ confirm: true });
    expect(request?.headers["x-requested-with"]).toBe("fitia");
    expect(await screen.findByText(/Tu cuenta y tus datos se eliminaron/)).toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: "Crear mi cuenta" }).length).toBeGreaterThan(0);
  });

  it("un 401 al eliminar (sesión ya cerrada) termina igual en la bienvenida", async () => {
    server.use(http.post(`${API}/me/delete-account`, () => apiError(401, "UNAUTHENTICATED", "x")));
    const { user, router } = renderRoute("/perfil/eliminar-cuenta", { me: ME });
    await user.click(await screen.findByRole("checkbox", { name: "Entiendo que es definitivo." }));
    await user.click(screen.getByRole("button", { name: "Eliminar mi cuenta" }));
    await waitFor(() => expect(pathOf(router)).toBe("/"));
  });

  it("cerrar sesión con 401 (ya estaba cerrada) limpia el estado y lleva a la bienvenida", async () => {
    server.use(
      http.get(`${API}/profile`, () => ok({ profile: PROFILE })),
      http.get(`${API}/onboarding/questionnaire`, () => ok(QUESTIONNAIRE)),
      http.post(`${API}/auth/logout`, () => apiError(401, "UNAUTHENTICATED", "x")),
    );
    const { user, router } = renderRoute("/perfil", { me: ME });
    await user.click(await screen.findByRole("button", { name: "Cerrar sesión" }));
    await waitFor(() => expect(pathOf(router)).toBe("/"));
    expect(await screen.findByText("Cerraste sesión.")).toBeInTheDocument();
    expect(screen.queryByRole("navigation", { name: "Navegación principal" })).not.toBeInTheDocument();
  });

  it("desde el diagnóstico también se puede cerrar sesión", async () => {
    server.use(
      http.get(`${API}/onboarding/questionnaire`, () => ok(QUESTIONNAIRE)),
      http.post(`${API}/auth/logout`, () => new HttpResponse(null, { status: 204 })),
    );
    const { user, router } = renderRoute("/diagnostico", { me: { ...ME, onboarding_completed: false } });
    await user.click(await screen.findByRole("button", { name: "Cuenta" }));
    expect(screen.getByRole("link", { name: "Eliminar mi cuenta" })).toHaveAttribute("href", "/perfil/eliminar-cuenta");
    await user.click(screen.getByRole("button", { name: "Cerrar sesión" }));
    await waitFor(() => expect(pathOf(router)).toBe("/"));
    expect(sent("POST", "/auth/logout")).toHaveLength(1);
  });

  it("tras cerrar sesión, entrar a una ruta protegida vuelve a pedir login", async () => {
    server.use(
      http.get(`${API}/profile`, () => ok({ profile: PROFILE })),
      http.get(`${API}/onboarding/questionnaire`, () => ok(QUESTIONNAIRE)),
      http.post(`${API}/auth/logout`, () => new HttpResponse(null, { status: 204 })),
    );
    const { user, router } = renderRoute("/perfil", { me: ME });
    await user.click(await screen.findByRole("button", { name: "Cerrar sesión" }));
    expect(await screen.findByText("Cerraste sesión.")).toBeInTheDocument();
    await router.navigate("/perfil");
    await waitFor(() => expect(pathOf(router)).toBe("/iniciar-sesion?volver=%2Fperfil"));
  });
});
