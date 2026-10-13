import { screen, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ME } from "../fixtures";
import { pathOf, renderRoute } from "../render";
import { API, apiError, http, ok, sent, server } from "../server";

const USER = { id: ME.id, nickname: "Pantera", program: ME.program };

describe("HU 1 — verificación del correo", () => {
  it("consume el token con UN solo POST aunque la app corra en StrictMode", async () => {
    server.use(http.post(`${API}/auth/verify-email`, () => ok({ user: USER, next: "onboarding" })));
    renderRoute("/verificar-correo?token=abc123", { strict: true });

    expect(await screen.findByText("¡Listo, Pantera! Tu correo quedó verificado.")).toBeInTheDocument();
    await new Promise((r) => setTimeout(r, 50));
    const posts = sent("POST", "/auth/verify-email");
    expect(posts).toHaveLength(1);
    expect(posts[0]?.body).toEqual({ token: "abc123" });
    expect(sent("GET", "/auth/verify-email")).toHaveLength(0);
  });

  it("tras verificar actualiza la sesión y lleva al diagnóstico", async () => {
    server.use(
      http.post(`${API}/auth/verify-email`, () => ok({ user: USER, next: "onboarding" })),
      http.get(`${API}/onboarding/questionnaire`, () => ok({ questions: [] })),
    );
    const { user, router } = renderRoute("/verificar-correo?token=abc123");
    await user.click(await screen.findByRole("link", { name: "Continuar" }));
    await waitFor(() => expect(pathOf(router)).toBe("/diagnostico"));
  });

  it("410 explica que el enlace venció u ocurrió ya, y permite pedir uno nuevo", async () => {
    server.use(
      http.post(`${API}/auth/verify-email`, () =>
        apiError(410, "TOKEN_EXPIRED_OR_USED", "El enlace de verificación venció o ya fue usado. Solicita uno nuevo."),
      ),
      http.post(`${API}/auth/resend-verification`, () => ok({ status: "accepted", message: "" }, 202)),
    );
    const { user } = renderRoute("/verificar-correo?token=viejo", { strict: true });

    expect(await screen.findByText("Este enlace venció o ya se usó.")).toBeInTheDocument();
    expect(sent("POST", "/auth/verify-email")).toHaveLength(1);
    await user.type(screen.getByLabelText("Tu correo institucional"), "ana@correounivalle.edu.co");
    await user.click(screen.getByRole("button", { name: "Enviarme un enlace nuevo" }));
    expect(await screen.findByText(/Si hay una cuenta pendiente/)).toBeInTheDocument();
  });

  it("410 con sesión activa ofrece ir a la app", async () => {
    server.use(http.post(`${API}/auth/verify-email`, () => apiError(410, "TOKEN_EXPIRED_OR_USED", "Venció.")));
    renderRoute("/verificar-correo?token=viejo", { me: ME });
    expect(await screen.findByRole("link", { name: "Ir a FITIA" })).toHaveAttribute("href", "/inicio");
  });

  it("sin token en la URL no llama a la API y ofrece reenviar", async () => {
    renderRoute("/verificar-correo");
    expect(await screen.findByText("Este enlace no es válido.")).toBeInTheDocument();
    expect(sent("POST", "/auth/verify-email")).toHaveLength(0);
  });
});
