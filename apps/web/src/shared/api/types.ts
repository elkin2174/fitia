/** Contratos de la API de FITIA (/api/v1). Reflejan exactamente las respuestas del backend. */

export interface Program {
  code: string;
  name: string;
}

export interface SessionUser {
  id: string;
  nickname: string;
  program: Program;
}

export interface MeResponse extends SessionUser {
  onboarding_completed: boolean;
}

export type NextStep = "onboarding" | "home";

export interface AuthResult {
  user: SessionUser;
  next: NextStep;
}

/** Código de opción tal como viene en el cuestionario: se envía con su tipo JSON original. */
export type OptionCode = string | number | boolean;

export interface QuestionOption {
  code: OptionCode;
  label: string;
}

export interface Question {
  id: string;
  text: string;
  type: "single" | "multi";
  options: QuestionOption[];
}

export interface QuestionnaireResponse {
  questions: Question[];
}

export type PlanStatus = "none" | "generating" | "ready" | "failed";
export type PlanDayStatus = "training" | "rest" | "unplanned" | "completed";
export type PlanFailureCode = "GENERATION_TIMEOUT" | "AI_UNAVAILABLE" | "AI_INVALID_OUTPUT" | "STALE";

export interface PlanDay {
  date: string;
  weekday: number;
  status: PlanDayStatus;
  title: string | null;
  estimated_minutes: number | null;
}

export interface CurrentPlan {
  status: PlanStatus;
  regenerating: boolean;
  week_start: string;
  start_date: string;
  generation_number: number;
  outdated: boolean;
  can_regenerate: boolean;
  failure: { code: PlanFailureCode | string } | null;
  days: PlanDay[];
}

export interface GeneratePlanResponse {
  plan_id: string;
  status: "generating";
}

export interface ExerciseGuide {
  steps: string[];
  disclaimer: string;
}

export interface PlanExercise {
  id: string;
  position: number;
  name: string;
  sets: number;
  reps: number | null;
  work_seconds: number | null;
  rest_seconds: number;
  guide: ExerciseGuide;
}

export interface PlanDayDetail {
  date: string;
  weekday: number;
  status: PlanDayStatus;
  title: string | null;
  estimated_minutes: number | null;
  exercises: PlanExercise[];
}

export interface NextTrainingDay {
  date: string;
  weekday: number;
  title: string | null;
  planned: boolean;
}

export interface TodayPlan {
  date: string;
  is_weekend: boolean;
  plan_status: PlanStatus;
  regenerating: boolean;
  failure: { code: PlanFailureCode | string } | null;
  day: PlanDayDetail | null;
  next_training_day: NextTrainingDay | null;
}

export interface ExerciseGuideResponse {
  exercise_id: string;
  name: string;
  steps: string[];
  disclaimer: string;
}

export interface RankingItem {
  position: number;
  nickname: string;
  points: number;
  level: number;
}

export interface RankingResponse {
  items: RankingItem[];
}
