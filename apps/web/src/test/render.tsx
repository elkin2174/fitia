import { QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { StrictMode } from "react";
import { createMemoryRouter } from "react-router";
import { RouterProvider } from "react-router/dom";
import { routes } from "../app/routes";
import { createQueryClient } from "../shared/api/queryClient";
import type { MeResponse } from "../shared/api/types";
import { ToastProvider } from "../shared/ui/Toast";
import { API, apiError, http, ok, server } from "./server";

/** Monta la app real (rutas, guards, providers) en memoria, en la ruta indicada. */
export function renderRoute(path: string, options: { me?: MeResponse | null; strict?: boolean; advanceTimers?: (ms: number) => void } = {}) {
  const { me = null, strict = false } = options;
  server.use(http.get(`${API}/me`, () => (me ? ok(me) : apiError(401, "UNAUTHENTICATED", "Debes iniciar sesión para continuar."))));
  const router = createMemoryRouter(routes, { initialEntries: [path] });
  const queryClient = createQueryClient();
  const app = (
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <RouterProvider router={router} />
      </ToastProvider>
    </QueryClientProvider>
  );
  const user = userEvent.setup(options.advanceTimers ? { advanceTimers: options.advanceTimers } : undefined);
  return { user, router, queryClient, ...render(strict ? <StrictMode>{app}</StrictMode> : app) };
}

export const pathOf = (router: { state: { location: { pathname: string; search: string } } }) =>
  router.state.location.pathname + router.state.location.search;
