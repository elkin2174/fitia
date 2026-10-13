/** Fechas en español y en la zona de Univalle (America/Bogota). */
export const TIME_ZONE = "America/Bogota";
const LOCALE = "es-CO";

export const WEEKDAY_NAMES: Record<number, string> = {
  1: "lunes",
  2: "martes",
  3: "miércoles",
  4: "jueves",
  5: "viernes",
  6: "sábado",
  7: "domingo",
};
export const WEEKDAY_SHORT: Record<number, string> = { 1: "L", 2: "M", 3: "X", 4: "J", 5: "V" };

/** "2026-10-12" → Date al mediodía de Bogotá (evita saltos de día por zona horaria). */
export function parseIsoDate(isoDate: string): Date {
  return new Date(`${isoDate}T12:00:00-05:00`);
}

function format(date: Date, options: Intl.DateTimeFormatOptions): string {
  return new Intl.DateTimeFormat(LOCALE, { timeZone: TIME_ZONE, ...options }).format(date);
}

/** "lunes 12 de octubre" */
export function formatDayLong(isoDate: string): string {
  return format(parseIsoDate(isoDate), { weekday: "long", day: "numeric", month: "long" }).replace(",", "");
}

/** "12 de octubre" */
export function formatDayMonth(isoDate: string): string {
  return format(parseIsoDate(isoDate), { day: "numeric", month: "long" });
}

/** "12 de octubre de 2026" a partir de un timestamp ISO del backend. */
export function formatDateFromTimestamp(timestamp: string): string {
  return format(new Date(timestamp), { day: "numeric", month: "long", year: "numeric" });
}

/** "12 oct" (para ejes de gráficas). */
export function formatShortFromTimestamp(timestamp: string): string {
  return format(new Date(timestamp), { day: "numeric", month: "short" }).replace(".", "");
}

/** Fecha de hoy en Bogotá como "YYYY-MM-DD". */
export function todayInBogota(now: Date = new Date()): string {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: TIME_ZONE,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(now);
  const get = (type: string) => parts.find((p) => p.type === type)?.value ?? "";
  return `${get("year")}-${get("month")}-${get("day")}`;
}
