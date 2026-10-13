import { api } from "../../shared/api/client";
import type { PhysicalHistoryResponse, ProfileResponse, ProfileUpdate, UpdateProfileResponse } from "./types";

export const profileKey = ["profile"] as const;
export const measurementsKey = ["measurements"] as const;

export const profileApi = {
  get: (options?: { silentAuth?: boolean }) => api.get<ProfileResponse>("/profile", options),
  /** Solo los campos que cambiaron; nunca points, level, ranking_position ni physical_updated_at. */
  update: (changes: ProfileUpdate) => api.patch<UpdateProfileResponse>("/profile", changes),
  measurements: () => api.get<PhysicalHistoryResponse>("/profile/measurements"),
};
