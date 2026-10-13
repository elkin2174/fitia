/**
 * Cliente HTTP único de FITIA.
 * - Toda petición va con credentials: "include" (cookie HttpOnly fitia_session; el cliente nunca ve el token).
 * - Toda mutación lleva X-Requested-With: fitia (protección CSRF exigida por el backend).
 * - Los errores se normalizan a ApiError con el formato uniforme { error: { code, message, fields } }.
 */

export const API_BASE_URL: string = (import.meta.env.VITE_API_URL as string | undefined) ?? "/api/v1";

export interface FieldErrorItem {
  field: string;
  code: string;
}

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly fields: FieldErrorItem[];
  /** Segundos de espera indicados por Retry-After (429). */
  readonly retryAfter?: number;

  constructor(status: number, code: string, message: string, fields: FieldErrorItem[] = [], retryAfter?: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.fields = fields;
    this.retryAfter = retryAfter;
  }

  fieldCodes(): Record<string, string> {
    return Object.fromEntries(this.fields.map((f) => [f.field, f.code]));
  }
}

export const NETWORK_ERROR = "NETWORK_ERROR";

type AuthEvent = "unauthenticated" | "onboarding_required";
type AuthListener = (event: AuthEvent) => void;
let authListener: AuthListener | null = null;

/** La app registra aquí qué hacer ante 401 UNAUTHENTICATED / 403 ONBOARDING_REQUIRED (ver app/AuthBridge). */
export function setAuthListener(listener: AuthListener | null): void {
  authListener = listener;
}

const MUTATING = new Set(["POST", "PUT", "PATCH", "DELETE"]);

export interface RequestOptions {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  body?: unknown;
  signal?: AbortSignal;
  /**
   * No disparar la redirección global ante 401/403. Para /me (visitante), logout y eliminar cuenta
   * (un 401 significa "ya estaba cerrada"), y consultas opcionales con sesión.
   */
  silentAuth?: boolean;
}

function parseRetryAfter(header: string | null): number | undefined {
  if (!header) return undefined;
  const seconds = Number(header);
  return Number.isFinite(seconds) && seconds >= 0 ? seconds : undefined;
}

async function toApiError(response: Response): Promise<ApiError> {
  const retryAfter = parseRetryAfter(response.headers.get("Retry-After"));
  let payload: unknown = null;
  try {
    payload = await response.json();
  } catch {
    payload = null;
  }
  const error = (payload as { error?: { code?: unknown; message?: unknown; fields?: unknown } } | null)?.error;
  if (error && typeof error.code === "string") {
    const fields = Array.isArray(error.fields)
      ? (error.fields as FieldErrorItem[]).filter((f) => typeof f?.field === "string" && typeof f?.code === "string")
      : [];
    const message = typeof error.message === "string" ? error.message : "";
    return new ApiError(response.status, error.code, message, fields, retryAfter);
  }
  return new ApiError(
    response.status,
    response.status >= 500 ? "INTERNAL_ERROR" : "HTTP_ERROR",
    "Algo salió mal. Intenta de nuevo en unos segundos.",
    [],
    retryAfter,
  );
}

export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const method = options.method ?? "GET";
  const headers: Record<string, string> = { Accept: "application/json" };
  if (MUTATING.has(method)) headers["X-Requested-With"] = "fitia";
  if (options.body !== undefined) headers["Content-Type"] = "application/json";

  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      method,
      headers,
      credentials: "include",
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
      signal: options.signal,
    });
  } catch (cause) {
    if ((cause as Error)?.name === "AbortError") throw cause;
    throw new ApiError(0, NETWORK_ERROR, "No pudimos conectarnos. Revisa tu conexión e intenta de nuevo.");
  }

  if (!response.ok) {
    const error = await toApiError(response);
    if (!options.silentAuth) {
      if (error.status === 401 && error.code === "UNAUTHENTICATED") authListener?.("unauthenticated");
      if (error.status === 403 && error.code === "ONBOARDING_REQUIRED") authListener?.("onboarding_required");
    }
    throw error;
  }
  if (response.status === 204) return undefined as T;
  const text = await response.text();
  return (text ? JSON.parse(text) : undefined) as T;
}

export const api = {
  get: <T>(path: string, options?: Omit<RequestOptions, "method" | "body">) => apiRequest<T>(path, { ...options }),
  post: <T>(path: string, body?: unknown, options?: Omit<RequestOptions, "method" | "body">) =>
    apiRequest<T>(path, { ...options, method: "POST", body }),
  patch: <T>(path: string, body: unknown, options?: Omit<RequestOptions, "method" | "body">) =>
    apiRequest<T>(path, { ...options, method: "PATCH", body }),
};

export function isApiError(error: unknown, code?: string): error is ApiError {
  return error instanceof ApiError && (code === undefined || error.code === code);
}
