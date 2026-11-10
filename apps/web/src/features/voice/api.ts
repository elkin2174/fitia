import { API_BASE_URL, ApiError, NETWORK_ERROR, type FieldErrorItem } from "../../shared/api/client";

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
    "Algo salió mal al preparar el audio. Intenta de nuevo.",
    [],
    retryAfter,
  );
}

/**
 * Solicita el audio en formato WAV para el ejercicio indicado.
 * Utiliza credenciales de sesión ('include') y normaliza errores a ApiError.
 */
export async function fetchExerciseAudio(exerciseId: string, signal?: AbortSignal): Promise<Blob> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/plan/exercises/${exerciseId}/audio`, {
      method: "GET",
      headers: {
        Accept: "audio/wav, application/json",
      },
      credentials: "include",
      signal,
    });
  } catch (cause) {
    if ((cause as Error)?.name === "AbortError") throw cause;
    throw new ApiError(0, NETWORK_ERROR, "No pudimos conectarnos. Revisa tu conexión e intenta de nuevo.");
  }

  if (!response.ok) {
    throw await toApiError(response);
  }

  return await response.blob();
}
