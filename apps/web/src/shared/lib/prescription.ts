/**
 * Formateo accesible y consistente de prescripciones de ejercicios (series, repeticiones, tiempo y descanso).
 */
export interface PrescriptionInput {
  sets: number;
  reps: number | null;
  work_seconds: number | null;
  rest_seconds: number;
}

export function formatSets(sets: number): string {
  return sets === 1 ? "1 serie" : `${sets} series`;
}

export function formatWork(reps: number | null, work_seconds: number | null): string {
  if (reps !== null && reps !== undefined) {
    return reps === 1 ? "1 repetición" : `${reps} repeticiones`;
  }
  if (work_seconds !== null && work_seconds !== undefined) {
    return `${work_seconds} s`;
  }
  return "";
}

export function formatRest(rest_seconds: number): string {
  return `Descanso ${rest_seconds} s`;
}

export function formatPrescriptionSummary(prescription: PrescriptionInput): string {
  const sets = formatSets(prescription.sets);
  const work = formatWork(prescription.reps, prescription.work_seconds);
  const rest = formatRest(prescription.rest_seconds);
  return `${sets} · ${work} · ${rest}`;
}

export function formatPrescriptionAriaLabel(prescription: PrescriptionInput, exerciseName?: string): string {
  const sets = prescription.sets === 1 ? "1 serie" : `${prescription.sets} series`;
  const work =
    prescription.reps !== null && prescription.reps !== undefined
      ? prescription.reps === 1
        ? "1 repetición"
        : `${prescription.reps} repeticiones`
      : `${prescription.work_seconds} segundos`;
  const rest = `descanso de ${prescription.rest_seconds} segundos`;
  const prefix = exerciseName ? `${exerciseName}: ` : "";
  return `${prefix}${sets}, ${work}, ${rest}`;
}
