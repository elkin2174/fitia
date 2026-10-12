export type Goal = "general_health" | "strength" | "endurance" | "weight_loss";
export type TermWeeks = 4 | 8 | 12;
export type FitnessLevel = "beginner" | "intermediate" | "advanced";
export type SessionMinutes = 15 | 30 | 45 | 60;
export type Weekday = 1 | 2 | 3 | 4 | 5;

export interface DiagnosticProfile {
  goal: Goal;
  term_weeks: TermWeeks;
  fitness_level: FitnessLevel;
  session_minutes: SessionMinutes;
  training_days: Weekday[];
  has_machine_access: boolean;
}

export interface ProfileResponse {
  profile: DiagnosticProfile;
}

export interface UpdateProfileResponse {
  profile: DiagnosticProfile;
  message: string;
}

export interface OptionItem<T> {
  value: T;
  label: string;
}

export const GOAL_OPTIONS: OptionItem<Goal>[] = [
  { value: "general_health", label: "Salud general y bienestar" },
  { value: "strength", label: "Aumento de fuerza y masa muscular" },
  { value: "endurance", label: "Resistencia cardiovascular y tono" },
  { value: "weight_loss", label: "Pérdida de grasa corporal" },
];

export const TERM_WEEKS_OPTIONS: OptionItem<TermWeeks>[] = [
  { value: 4, label: "4 semanas (1 mes)" },
  { value: 8, label: "8 semanas (2 meses)" },
  { value: 12, label: "12 semanas (3 meses)" },
];

export const FITNESS_LEVEL_OPTIONS: OptionItem<FitnessLevel>[] = [
  { value: "beginner", label: "Principiante (poco o ningún entrenamiento previo)" },
  { value: "intermediate", label: "Intermedio (entreno con cierta regularidad)" },
  { value: "advanced", label: "Avanzado (entrenamiento estructurado constante)" },
];

export const SESSION_MINUTES_OPTIONS: OptionItem<SessionMinutes>[] = [
  { value: 15, label: "15 minutos (sesión express)" },
  { value: 30, label: "30 minutos" },
  { value: 45, label: "45 minutos" },
  { value: 60, label: "60 minutos (sesión completa)" },
];

export const WEEKDAY_OPTIONS: OptionItem<Weekday>[] = [
  { value: 1, label: "Lunes" },
  { value: 2, label: "Martes" },
  { value: 3, label: "Miércoles" },
  { value: 4, label: "Jueves" },
  { value: 5, label: "Viernes" },
];
