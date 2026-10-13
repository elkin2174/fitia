import { beforeEach, describe, expect, it, vi } from "vitest";
import { API, apiError, http, HttpResponse, ok, requests, server } from "../../test/server";
import { ApiError, api, setAuthListener } from "./client";

describe("apiClient", () => {
  // credentials se verifica en la llamada a fetch: el Request que reconstruye MSW en Node no lo conserva.
  const fetchInit = () => (fetchSpy.mock.calls.at(-1)?.[1] ?? {}) as RequestInit;
  let fetchSpy: ReturnType<typeof vi.spyOn>;
  beforeEach(() => {
    fetchSpy = vi.spyOn(globalThis, "fetch");
  });

  it("toda petición usa credentials include; GET sin encabezado CSRF", async () => {
    server.use(http.get(`${API}/programs`, () => ok([])));
    await api.get("/programs");
    expect(fetchInit().credentials).toBe("include");
    expect(requests[0]?.headers["x-requested-with"]).toBeUndefined();
  });

  it.each(["post", "patch"] as const)("las mutaciones (%s) llevan X-Requested-With: fitia y JSON", async (method) => {
    server.use(http[method](`${API}/algo`, () => ok({})));
    await (method === "post" ? api.post("/algo", { a: 1 }) : api.patch("/algo", { a: 1 }));
    expect(requests[0]?.headers["x-requested-with"]).toBe("fitia");
    expect(requests[0]?.headers["content-type"]).toBe("application/json");
    expect(requests[0]?.body).toEqual({ a: 1 });
    expect(fetchInit().credentials).toBe("include");
  });

  it("el POST sin cuerpo también lleva el encabezado CSRF", async () => {
    server.use(http.post(`${API}/plan/generate`, () => ok({ plan_id: "x", status: "generating" }, 202)));
    await api.post("/plan/generate");
    expect(requests[0]?.headers["x-requested-with"]).toBe("fitia");
  });

  it("parsea el formato uniforme de error con campos y Retry-After", async () => {
    server.use(
      http.post(`${API}/auth/register`, () =>
        apiError(429, "RATE_LIMITED", "Demasiados intentos.", [{ field: "email", code: "X" }], { "Retry-After": "720" }),
      ),
    );
    const error = await api.post("/auth/register", {}).catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ status: 429, code: "RATE_LIMITED", message: "Demasiados intentos.", retryAfter: 720 });
    expect((error as ApiError).fieldCodes()).toEqual({ email: "X" });
  });

  it("un 500 sin el formato da un mensaje amable", async () => {
    server.use(http.get(`${API}/me`, () => new HttpResponse("boom", { status: 500 })));
    await expect(api.get("/me")).rejects.toMatchObject({ status: 500, code: "INTERNAL_ERROR" });
  });

  it("un 204 devuelve undefined", async () => {
    server.use(http.post(`${API}/auth/logout`, () => new HttpResponse(null, { status: 204 })));
    await expect(api.post("/auth/logout")).resolves.toBeUndefined();
  });

  it("401 UNAUTHENTICATED y 403 ONBOARDING_REQUIRED avisan a la app, salvo con silentAuth", async () => {
    const listener = vi.fn();
    setAuthListener(listener);
    server.use(
      http.get(`${API}/profile`, () => apiError(401, "UNAUTHENTICATED")),
      http.get(`${API}/plan/current`, () => apiError(403, "ONBOARDING_REQUIRED")),
    );
    await api.get("/profile").catch(() => {});
    await api.get("/plan/current").catch(() => {});
    await api.get("/profile", { silentAuth: true }).catch(() => {});
    expect(listener.mock.calls).toEqual([["unauthenticated"], ["onboarding_required"]]);
  });

  it("un 401 de credenciales incorrectas no dispara la redirección", async () => {
    const listener = vi.fn();
    setAuthListener(listener);
    server.use(http.post(`${API}/auth/login`, () => apiError(401, "INVALID_CREDENTIALS")));
    await api.post("/auth/login", {}).catch(() => {});
    expect(listener).not.toHaveBeenCalled();
  });

  it("una caída de red se convierte en NETWORK_ERROR", async () => {
    server.use(http.get(`${API}/programs`, () => HttpResponse.error()));
    await expect(api.get("/programs")).rejects.toMatchObject({ code: "NETWORK_ERROR", status: 0 });
  });
});
