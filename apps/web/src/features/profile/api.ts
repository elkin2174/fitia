import type { DiagnosticProfile, ProfileResponse, UpdateProfileResponse } from "./types";

const BASE_URL = "/api/v1/profile";

export async function getProfile(): Promise<ProfileResponse> {
  const response = await fetch(BASE_URL, {
    method: "GET",
    headers: {
      "Accept": "application/json",
    },
    credentials: "include", // incluye la cookie fitia_session
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.message || `Error al consultar el perfil (${response.status})`);
  }

  return response.json();
}

export async function updateProfile(
  payload: Partial<DiagnosticProfile>
): Promise<UpdateProfileResponse> {
  const response = await fetch(BASE_URL, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
      "Accept": "application/json",
      "X-Requested-With": "fitia", // Cabecera anti-CSRF requerida por el backend
    },
    credentials: "include",
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.message || `Error al actualizar el perfil (${response.status})`);
  }

  return response.json();
}
