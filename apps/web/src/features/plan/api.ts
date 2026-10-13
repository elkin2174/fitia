import { api } from "../../shared/api/client";
import type { CurrentPlan, GeneratePlanResponse } from "../../shared/api/types";

export const planKey = ["plan"] as const;

export const planApi = {
  /** Solo lee: nunca dispara la IA (NFR-16). */
  current: () => api.get<CurrentPlan>("/plan/current"),
  generate: () => api.post<GeneratePlanResponse>("/plan/generate"),
};
