import { HttpResponse, http, type JsonBodyType } from "msw";
import { setupServer } from "msw/node";

export const API = "http://localhost/api/v1";
export const server = setupServer();

export interface Recorded {
  method: string;
  path: string;
  body: unknown;
  headers: Record<string, string>;
  credentials: string;
}

/** Guarda cada petición que llega a la API simulada (para verificar cuerpos, tipos y encabezados). */
export const requests: Recorded[] = [];
server.events.on("request:start", async ({ request }) => {
  let body: unknown;
  try {
    const text = await request.clone().text();
    body = text ? JSON.parse(text) : undefined;
  } catch {
    body = undefined;
  }
  requests.push({
    method: request.method,
    path: new URL(request.url).pathname.replace("/api/v1", ""),
    body,
    headers: Object.fromEntries(request.headers.entries()),
    credentials: request.credentials,
  });
});
afterEach(() => {
  requests.length = 0;
});

export const sent = (method: string, path: string) => requests.filter((r) => r.method === method && r.path === path);

export function apiError(status: number, code: string, message = "", fields: Array<{ field: string; code: string }> = [], headers?: Record<string, string>) {
  return HttpResponse.json({ error: { code, message, fields } }, { status, headers });
}

export const ok = (body: JsonBodyType, status = 200) => HttpResponse.json(body, { status });
export { HttpResponse, http };
