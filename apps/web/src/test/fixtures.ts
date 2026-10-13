import type { CurrentPlan, MeResponse, QuestionnaireResponse } from "../shared/api/types";
import type { StudentProfile } from "../features/profile/types";

export const ME: MeResponse = {
  id: "11111111-1111-1111-1111-111111111111",
  nickname: "Pantera",
  program: { code: "ING-SIS", name: "Ingeniería de Sistemas" },
  onboarding_completed: true,
};
export const ME_NO_PROFILE: MeResponse = { ...ME, onboarding_completed: false };

export const PROGRAMS = [
  { code: "ADM", name: "Administración de Empresas" },
  { code: "ING-SIS", name: "Ingeniería de Sistemas" },
  { code: "MED", name: "Medicina y Cirugía" },
];

/** Igual al que entrega GET /onboarding/questionnaire (HU 4). */
export const QUESTIONNAIRE: QuestionnaireResponse = {
  questions: [
    { id: "goal", text: "¿Cuál es tu objetivo principal?", type: "single", options: [
      { code: "general_health", label: "Salud general" }, { code: "strength", label: "Fuerza" },
      { code: "endurance", label: "Resistencia" }, { code: "weight_loss", label: "Pérdida de peso" } ] },
    { id: "term_weeks", text: "¿En cuánto tiempo quieres lograrlo?", type: "single", options: [
      { code: 4, label: "4 semanas" }, { code: 8, label: "8 semanas" }, { code: 12, label: "12 semanas" } ] },
    { id: "fitness_level", text: "¿Cuál es tu nivel físico actual?", type: "single", options: [
      { code: "beginner", label: "Principiante" }, { code: "intermediate", label: "Intermedio" }, { code: "advanced", label: "Avanzado" } ] },
    { id: "session_minutes", text: "¿Cuánto tiempo tienes disponible por sesión?", type: "single", options: [
      { code: 15, label: "15 min" }, { code: 30, label: "30 min" }, { code: 45, label: "45 min" }, { code: 60, label: "60 min" } ] },
    { id: "has_machine_access", text: "¿Tienes acceso a máquinas (gimnasio)?", type: "single", options: [
      { code: true, label: "Sí" }, { code: false, label: "No" } ] },
    { id: "training_days", text: "¿Qué días puedes entrenar? Elige uno o más.", type: "multi", options: [
      { code: 1, label: "Lunes" }, { code: 2, label: "Martes" }, { code: 3, label: "Miércoles" }, { code: 4, label: "Jueves" }, { code: 5, label: "Viernes" } ] },
  ],
};

export const PROFILE: StudentProfile = {
  goal: "strength",
  term_weeks: 8,
  fitness_level: "beginner",
  session_minutes: 30,
  training_days: [1, 3, 5],
  has_machine_access: false,
  weight_kg: null,
  height_cm: null,
  physical_updated_at: null,
  is_public_ranking: true,
  points: 0,
  level: 1,
  ranking_position: 1,
};

const WEEK = ["2026-10-12", "2026-10-13", "2026-10-14", "2026-10-15", "2026-10-16"];
export function plan(overrides: Partial<CurrentPlan> = {}): CurrentPlan {
  const ready = (overrides.status ?? "ready") === "ready";
  return {
    status: "ready",
    regenerating: false,
    week_start: WEEK[0]!,
    start_date: WEEK[0]!,
    generation_number: ready ? 1 : 0,
    outdated: false,
    can_regenerate: false,
    failure: null,
    days: WEEK.map((date, i) => {
      const weekday = i + 1;
      const training = ready && [1, 3, 5].includes(weekday);
      return {
        date,
        weekday,
        status: ready ? (training ? "training" : "rest") : "unplanned",
        title: training ? `Rutina del día ${weekday}` : null,
        estimated_minutes: training ? 25 : null,
      };
    }),
    ...overrides,
  };
}
