import { useQuery, useQueryClient, type QueryClient } from "@tanstack/react-query";
import { api, isApiError } from "../api/client";
import type { MeResponse, SessionUser } from "../api/types";

export const meKey = ["me"] as const;
/** Motivo de un cierre de sesión intencional (logout o cuenta eliminada). */
export type SessionEndNotice = "logged_out" | "account_deleted";
const endedKey = ["session-ended"] as const;
/** Datos que pertenecen al usuario: se borran al cerrar sesión o eliminar la cuenta. */
export const USER_DATA_KEYS = [["plan"], ["profile"], ["measurements"]] as const;

async function fetchMe(): Promise<MeResponse | null> {
  try {
    return await api.get<MeResponse>("/me", { silentAuth: true });
  } catch (error) {
    if (isApiError(error) && error.status === 401) return null; // visitante
    throw error;
  }
}

/** Estado de sesión: undefined mientras carga, null sin sesión, MeResponse con sesión. */
export function useMe() {
  return useQuery({ queryKey: meKey, queryFn: fetchMe, staleTime: 5 * 60_000, retry: false });
}

/**
 * Fija el usuario de la sesión. Antes cancela cualquier GET /me en vuelo: si salió antes de que existiera
 * la cookie (p. ej. al abrir el enlace de verificación), su 401 llegaría después y borraría la sesión.
 */
export async function setSessionUser(client: QueryClient, user: SessionUser, onboardingCompleted: boolean): Promise<void> {
  await client.cancelQueries({ queryKey: meKey });
  client.setQueryData(endedKey, null);
  const me: MeResponse = { ...user, onboarding_completed: onboardingCompleted };
  client.setQueryData<MeResponse | null>(meKey, me);
}

export function markOnboarding(client: QueryClient, completed: boolean): void {
  client.setQueryData<MeResponse | null>(meKey, (me) => (me ? { ...me, onboarding_completed: completed } : me));
}

/**
 * Borra la sesión del cliente. Con `notice` el cierre es intencional: los guards de la pantalla que se
 * está dejando llevan a la bienvenida y no al login (sin depender del orden de los renders).
 */
export function clearSession(client: QueryClient, notice?: SessionEndNotice): void {
  for (const key of USER_DATA_KEYS) client.removeQueries({ queryKey: key });
  client.setQueryData(endedKey, notice ?? null);
  client.setQueryData(meKey, null);
}

export function sessionEndNotice(client: QueryClient): SessionEndNotice | null {
  return client.getQueryData<SessionEndNotice | null>(endedKey) ?? null;
}

export function forgetSessionEnd(client: QueryClient): void {
  client.setQueryData(endedKey, null);
}

export function useSessionActions() {
  const client = useQueryClient();
  return {
    setUser: (user: SessionUser, onboardingCompleted: boolean) => setSessionUser(client, user, onboardingCompleted),
    markOnboarding: (completed: boolean) => markOnboarding(client, completed),
    clear: (notice?: SessionEndNotice) => clearSession(client, notice),
  };
}

/** Ruta interna segura para volver tras iniciar sesión (evita redirecciones abiertas). */
export function safeReturnPath(value: string | null): string | null {
  if (!value || !value.startsWith("/") || value.startsWith("//")) return null;
  return value;
}
