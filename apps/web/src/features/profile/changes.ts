import type { EditableProfileFields, ProfileUpdate, StudentProfile } from "./types";

const EDITABLE: Array<keyof EditableProfileFields> = [
  "goal",
  "term_weeks",
  "fitness_level",
  "session_minutes",
  "training_days",
  "has_machine_access",
  "weight_kg",
  "height_cm",
  "is_public_ranking",
];

const sameValue = (a: unknown, b: unknown) =>
  Array.isArray(a) && Array.isArray(b)
    ? a.length === b.length && [...a].sort().every((v, i) => v === [...b].sort()[i])
    : a === b;

/** Devuelve SOLO los campos editables que cambiaron frente al perfil guardado. */
export function diffProfile(saved: StudentProfile, draft: Partial<Record<keyof EditableProfileFields, unknown>>): ProfileUpdate {
  const changes: Record<string, unknown> = {};
  for (const key of EDITABLE) {
    if (!(key in draft)) continue;
    const value = draft[key];
    if (value === undefined || value === null) continue;
    if (!sameValue(value, saved[key])) changes[key] = value;
  }
  return changes as ProfileUpdate;
}

export const hasChanges = (changes: ProfileUpdate) => Object.keys(changes).length > 0;
