import type { ApiError } from "../api/client";

/** Texto propio por (campo, código). El backend es la fuente de verdad; aquí solo se redacta para la UI. */
const MESSAGES: Record<string, string> = {
  "nickname:NICKNAME_LENGTH": "Tu apodo debe tener entre 3 y 20 caracteres.",
  "program_code:PROGRAM_REQUIRED": "Elige tu programa académico.",
  "accepted_terms:TERMS_REQUIRED": "Debes aceptar el tratamiento de datos para continuar.",
  "accepted_terms:INVALID": "Debes aceptar el tratamiento de datos para continuar.",
  "password:WEAK_PASSWORD": "La contraseña debe tener al menos 8 caracteres.",
  "password:PASSWORD_TOO_LONG": "La contraseña no puede tener más de 128 caracteres.",
  "password:REQUIRED": "Escribe tu contraseña.",
  "email:INVALID_EMAIL": "Revisa el formato de tu correo.",
  "email:DOMAIN_NOT_ALLOWED": "Solo se admiten correos @correounivalle.edu.co",
  "email:EMAIL_EXISTS": "Este correo ya tiene cuenta.",
  "weight_kg:INVALID_OPTION": "El peso debe estar entre 20 y 400 kg.",
  "weight_kg:REQUIRED": "Escribe tu peso en kilogramos.",
  "height_cm:INVALID_OPTION": "La estatura debe estar entre 50 y 270 cm.",
  "height_cm:REQUIRED": "Escribe tu estatura en centímetros.",
  "training_days:DAYS_REQUIRED": "Elige al menos un día para entrenar, de lunes a viernes.",
  "training_days:INVALID_OPTION": "Elige días de lunes a viernes.",
  "has_machine_access:MACHINE_ACCESS_REQUIRED": "Indica si tienes acceso a máquinas.",
  "*:REQUIRED": "Responde esta pregunta.",
  "*:INVALID_OPTION": "Elige una de las opciones disponibles.",
  "*:INVALID": "Revisa este dato.",
};

export function fieldMessage(field: string, code: string): string {
  return MESSAGES[`${field}:${code}`] ?? MESSAGES[`*:${code}`] ?? "Revisa este dato.";
}

/** { campo: mensaje } a partir de error.fields. */
export function fieldErrorsFrom(error: ApiError): Record<string, string> {
  return Object.fromEntries(error.fields.map((f) => [f.field, fieldMessage(f.field, f.code)]));
}
