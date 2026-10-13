import { describe, expect, it } from "vitest";
import { formatDayLong, formatDayMonth, todayInBogota } from "./dates";
import { describeWait, describeWaitUntilDay } from "./retryAfter";

describe("fechas en Bogotá", () => {
  it("formatea en español", () => {
    expect(formatDayLong("2026-10-12")).toBe("lunes 12 de octubre");
    expect(formatDayMonth("2026-10-19")).toBe("19 de octubre");
  });
  it("hoy se calcula en America/Bogota (UTC-5)", () => {
    // 03:00 UTC del 13 = 22:00 del 12 en Bogotá
    expect(todayInBogota(new Date("2026-10-13T03:00:00Z"))).toBe("2026-10-12");
  });
});

describe("Retry-After en lenguaje humano", () => {
  it.each([
    [1, "en 1 segundo"],
    [45, "en 45 segundos"],
    [60, "en 1 minuto"],
    [720, "en 12 minutos"],
    [3600, "en 1 hora"],
    [7200, "en 2 horas"],
    [172800, "en 2 días"],
  ])("%i s → %s", (seconds, text) => {
    expect(describeWait(seconds)).toBe(text);
  });
  it("una espera larga se expresa como el día", () => {
    // jueves 15-oct 10:00 Bogotá + 3 días y 14 h → lunes 19-oct 00:00 (como el Retry-After del backend)
    expect(describeWaitUntilDay(3 * 86400 + 14 * 3600, new Date("2026-10-15T15:00:00Z"))).toBe("el lunes 19 de octubre");
  });
});
