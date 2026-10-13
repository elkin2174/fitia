import { TIME_ZONE } from "./dates";

/** Convierte Retry-After (segundos) en texto: "en 45 segundos", "en 12 minutos", "en 2 horas". */
export function describeWait(seconds: number): string {
  if (seconds < 60) {
    const s = Math.max(1, Math.ceil(seconds));
    return `en ${s} ${s === 1 ? "segundo" : "segundos"}`;
  }
  if (seconds < 3600) {
    const m = Math.ceil(seconds / 60);
    return `en ${m} ${m === 1 ? "minuto" : "minutos"}`;
  }
  const h = Math.ceil(seconds / 3600);
  if (h < 24) return `en ${h} ${h === 1 ? "hora" : "horas"}`;
  const d = Math.ceil(seconds / 86400);
  return `en ${d} ${d === 1 ? "día" : "días"}`;
}

/** Día en que vence la espera: "el lunes 19 de octubre". */
export function describeWaitUntilDay(seconds: number, now: Date = new Date()): string {
  const target = new Date(now.getTime() + seconds * 1000);
  const text = new Intl.DateTimeFormat("es-CO", {
    timeZone: TIME_ZONE,
    weekday: "long",
    day: "numeric",
    month: "long",
  }).format(target);
  return `el ${text.replace(",", "")}`;
}
