import { api } from "../../shared/api/client";
import type { OptionCode, QuestionnaireResponse } from "../../shared/api/types";
import type { DiagnosticAnswers } from "../profile/types";

export type Answers = Record<string, OptionCode | number[]>;

export const onboardingApi = {
  questionnaire: () => api.get<QuestionnaireResponse>("/onboarding/questionnaire"),
  /** Los code viajan con su tipo JSON original (8, true, "strength"), sin convertir. */
  complete: (answers: Answers) => api.post<{ profile: DiagnosticAnswers }>("/onboarding/complete", answers),
};

export const questionnaireKey = ["questionnaire"] as const;
