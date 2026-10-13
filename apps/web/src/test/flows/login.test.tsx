import { screen, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ME } from "../fixtures";
import { pathOf, renderRoute } from "../render";
import { API, apiError, http, ok, sent, server } from "../server";

const USER = { id: ME.id, nickname: "Pantera", program: ME.program };

async function submit(user: ReturnType<typeof renderRoute>["user"], email = "ana@correounivalle.edu.co", password = "contrasena") {
  await user.type(await screen.findByLabelText("Correo institucional"), email);
  await user.type(screen.getByLabelText("Contraseña"), password);
  await user.click(screen.getByRole("button", { name: "Iniciar sesión" }));
}

describe("HU 2 — inicio de sesión", () => {
  it("next onboarding lleva al diagnóstico", async () => {
    server.use(
      http.post(`${API}/auth/login`, () => ok({ user: USER, next: "onboarding" })),
      http.get(`${API}/onboarding/questionnaire`, () => ok({ questions: [] })),
    );
    const { user, router } = renderRoute("/iniciar-sesion");
    await submit(user);
    await waitFor(() => expect(pathOf(router)).toBe("/diagnostico"));
    expect(sent("POST", "/auth/login")[0]?.headers["x-requested-with"]).toBe("fitia");
  });

  it("next home vuelve a la ruta guardada", async () => {
    server.use(
      http.post(`${API}/auth/login`, () => ok({ user: USER, next: "home" })),
      http.get(`${API}/profile`, () => ok({ profile: {} })),
    );
    const { user, router } = renderRoute("/iniciar-sesion?volver=%2Fperfil%2Fhistorial");
    server.use(http.get(`${API}/profile/measurements`, () => ok({ history: [] })));
    await submit(user);
    await waitFor(() => expect(pathOf(router)).toBe("/perfil/historial"));
  });

  it("no acepta rutas de retorno externas", async () => {
    server.use(
      http.post(`${API}/auth/login`, () => ok({ user: USER, next: "home" })),
      http.get(`${API}/plan/current`, () => apiError(500, "INTERNAL_ERROR", "x")),
    );
    const { user, router } = renderRoute("/iniciar-sesion?volver=%2F%2Fevil.com");
    await submit(user);
    await waitFor(() => expect(pathOf(router)).toBe("/inicio"));
  });

  it("INVALID_CREDENTIALS muestra un mensaje genérico sin marcar campos", async () => {
    server.use(http.post(`${API}/auth/login`, () => apiError(401, "INVALID_CREDENTIALS", "El correo o la contraseña no son correctos.")));
    const { user, router } = renderRoute("/iniciar-sesion");
    await submit(user);
    expect(await screen.findByText("El correo o la contraseña no son correctos.")).toBeInTheDocument();
    expect(screen.getByLabelText("Correo institucional")).not.toHaveAttribute("aria-invalid");
    expect(screen.getByLabelText("Contraseña")).not.toHaveAttribute("aria-invalid");
    expect(pathOf(router)).toBe("/iniciar-sesion"); // un 401 de credenciales no redirige
  });

  it("ACCOUNT_NOT_FOUND ofrece crear cuenta con el correo precargado", async () => {
    server.use(
      http.post(`${API}/auth/login`, () => apiError(404, "ACCOUNT_NOT_FOUND", "Este correo no está registrado en FITIA. Crea una cuenta para empezar.")),
      http.get(`${API}/programs`, () => ok([])),
    );
    const { user } = renderRoute("/iniciar-sesion");
    await submit(user, "nuevo@correounivalle.edu.co");
    const link = await screen.findByRole("link", { name: "Crear cuenta" });
    expect(screen.getByText(/no está registrado en FITIA/)).toBeInTheDocument();
    await user.click(link);
    expect(await screen.findByLabelText("Correo institucional")).toHaveValue("nuevo@correounivalle.edu.co");
  });

  it("EMAIL_NOT_VERIFIED permite reenviar el enlace al correo escrito", async () => {
    server.use(
      http.post(`${API}/auth/login`, () => apiError(403, "EMAIL_NOT_VERIFIED", "Debes verificar tu correo antes de iniciar sesión.")),
      http.post(`${API}/auth/resend-verification`, () => ok({ status: "accepted", message: "" }, 202)),
    );
    const { user } = renderRoute("/iniciar-sesion");
    await submit(user, "pendiente@correounivalle.edu.co");
    await user.click(await screen.findByRole("button", { name: "Reenviar enlace de verificación" }));
    await waitFor(() => expect(sent("POST", "/auth/resend-verification")[0]?.body).toEqual({ email: "pendiente@correounivalle.edu.co" }));
  });

  it("VALIDATION_ERROR marca los campos (sin mínimo de 8 en el login)", async () => {
    server.use(
      http.post(`${API}/auth/login`, () =>
        apiError(422, "VALIDATION_ERROR", "x", [{ field: "email", code: "INVALID_EMAIL" }]),
      ),
    );
    const { user } = renderRoute("/iniciar-sesion");
    await submit(user, "a@b.co", "corta"); // contraseña corta: no se bloquea en cliente
    expect(await screen.findByText("Revisa el formato de tu correo.")).toBeInTheDocument();
    expect(sent("POST", "/auth/login")[0]?.body).toEqual({ email: "a@b.co", password: "corta" });
  });

  it("RATE_LIMITED informa la espera y deshabilita el botón", async () => {
    server.use(http.post(`${API}/auth/login`, () => apiError(429, "RATE_LIMITED", "x", [], { "Retry-After": "720" })));
    const { user } = renderRoute("/iniciar-sesion");
    await submit(user);
    expect(await screen.findByText(/Demasiados intentos\. Intenta de nuevo en 12 minutos\./)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Espera 720 s/ })).toBeDisabled();
  });
});
