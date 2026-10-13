import { describe, expect, it } from "vitest";
import {
  formatPrescriptionAriaLabel,
  formatPrescriptionSummary,
  formatRest,
  formatSets,
  formatWork,
} from "./prescription";

describe("prescription formatting", () => {
  it("formats singular and plural sets correctly", () => {
    expect(formatSets(1)).toBe("1 serie");
    expect(formatSets(3)).toBe("3 series");
  });

  it("formats reps correctly", () => {
    expect(formatWork(1, null)).toBe("1 repetición");
    expect(formatWork(12, null)).toBe("12 repeticiones");
  });

  it("formats work seconds correctly", () => {
    expect(formatWork(null, 30)).toBe("30 s");
  });

  it("formats rest seconds correctly", () => {
    expect(formatRest(60)).toBe("Descanso 60 s");
  });

  it("formats summary line correctly", () => {
    expect(
      formatPrescriptionSummary({
        sets: 3,
        reps: 12,
        work_seconds: null,
        rest_seconds: 60,
      })
    ).toBe("3 series · 12 repeticiones · Descanso 60 s");

    expect(
      formatPrescriptionSummary({
        sets: 1,
        reps: null,
        work_seconds: 45,
        rest_seconds: 30,
      })
    ).toBe("1 serie · 45 s · Descanso 30 s");
  });

  it("formats full aria label for screen readers", () => {
    expect(
      formatPrescriptionAriaLabel(
        {
          sets: 3,
          reps: 12,
          work_seconds: null,
          rest_seconds: 60,
        },
        "Sentadilla libre"
      )
    ).toBe("Sentadilla libre: 3 series, 12 repeticiones, descanso de 60 segundos");

    expect(
      formatPrescriptionAriaLabel({
        sets: 1,
        reps: null,
        work_seconds: 30,
        rest_seconds: 15,
      })
    ).toBe("1 serie, 30 segundos, descanso de 15 segundos");
  });
});
