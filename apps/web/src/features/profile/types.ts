/**
 * Tipos del perfil (contrato de la HU 7). Solo tipos: las opciones y sus etiquetas salen
 * de GET /onboarding/questionnaire (la HU 4 exige que no haya listas de opciones en el cliente).
 */

export type Goal = "general_health" | "strength" | "endurance" | "weight_loss";
export type TermWeeks = 4 | 8 | 12;
export type FitnessLevel = "beginner" | "intermediate" | "advanced";
export type SessionMinutes = 15 | 30 | 45 | 60;
export type Weekday = 1 | 2 | 3 | 4 | 5;

export interface DiagnosticAnswers {
  goal: Goal;
  term_weeks: TermWeeks;
  fitness_level: FitnessLevel;
  session_minutes: SessionMinutes;
  training_days: Weekday[];
  has_machine_access: boolean;
}

export interface StudentProfile extends DiagnosticAnswers {
  weight_kg: number | null;
  height_cm: number | null;
  physical_updated_at: string | null;
  is_public_ranking: boolean;
  /** Solo lectura: nunca se envían en el PATCH (darían 422 NOT_EDITABLE). */
  points: number;
  level: number;
  ranking_position: number | null;
}

/** Únicos campos que acepta PATCH /profile. */
export type EditableProfileFields = DiagnosticAnswers & {
  weight_kg: number;
  height_cm: number;
  is_public_ranking: boolean;
};

export type ProfileUpdate = Partial<EditableProfileFields>;

export interface ProfileResponse {
  profile: StudentProfile;
}

export interface UpdateProfileResponse {
  profile: StudentProfile;
  message: string;
}

export interface PhysicalMeasurement {
  id: string;
  weight_kg: number | null;
  height_cm: number | null;
  recorded_at: string;
}

export interface PhysicalHistoryResponse {
  history: PhysicalMeasurement[];
}

export const WEIGHT_RANGE_KG = { min: 20, max: 400 } as const;
export const HEIGHT_RANGE_CM = { min: 50, max: 270 } as const;
