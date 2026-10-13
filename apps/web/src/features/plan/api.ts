import { api } from "../../shared/api/client";
import type {
  CurrentPlan,
  ExerciseGuideResponse,
  GeneratePlanResponse,
  PlanDayDetail,
  TodayPlan,
} from "../../shared/api/types";

export const planKey = ["plan"] as const;
export const todayKey = ["plan", "today"] as const;
export const dayKey = (date: string) => ["plan", "day", date] as const;
export const guideKey = (id: string) => ["plan", "guide", id] as const;

export const planApi = {
  /** Solo lee: nunca dispara la IA (NFR-16). */
  current: () => api.get<CurrentPlan>("/plan/current"),
  generate: () => api.post<GeneratePlanResponse>("/plan/generate"),
  today: () => api.get<TodayPlan>("/plan/today"),
  day: (date: string) => api.get<PlanDayDetail>(`/plan/days/${date}`),
  guide: (id: string) => api.get<ExerciseGuideResponse>(`/plan/exercises/${id}/guide`),
};
