import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  DEFAULT_PLAYBACK_RATE,
  PLAYBACK_RATE_STORAGE_KEY,
  isPlaybackRate,
  loadPlaybackRate,
  savePlaybackRate,
} from "./playbackRate";

describe("HU 5 — playbackRate", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  afterEach(() => {
    localStorage.clear();
    vi.restoreAllMocks();
  });

  it("isPlaybackRate valida solo 0.75, 1 y 1.25", () => {
    expect(isPlaybackRate(0.75)).toBe(true);
    expect(isPlaybackRate(1)).toBe(true);
    expect(isPlaybackRate(1.25)).toBe(true);
    expect(isPlaybackRate(2)).toBe(false);
    expect(isPlaybackRate("1")).toBe(false);
    expect(isPlaybackRate(null)).toBe(false);
  });

  it("loadPlaybackRate devuelve 1× por defecto si no hay nada guardado (AC-5-2)", () => {
    expect(loadPlaybackRate()).toBe(DEFAULT_PLAYBACK_RATE);
    expect(loadPlaybackRate()).toBe(1);
  });

  it("savePlaybackRate guarda y loadPlaybackRate recupera el valor guardado (AC-5-2)", () => {
    savePlaybackRate(1.25);
    expect(localStorage.getItem(PLAYBACK_RATE_STORAGE_KEY)).toBe("1.25");
    expect(loadPlaybackRate()).toBe(1.25);

    savePlaybackRate(0.75);
    expect(loadPlaybackRate()).toBe(0.75);
  });

  it("loadPlaybackRate devuelve 1× si el valor en localStorage es inválido", () => {
    localStorage.setItem(PLAYBACK_RATE_STORAGE_KEY, "invalido");
    expect(loadPlaybackRate()).toBe(1);

    localStorage.setItem(PLAYBACK_RATE_STORAGE_KEY, "2.0");
    expect(loadPlaybackRate()).toBe(1);
  });

  it("si localStorage falla o lanza excepción, se usa 1× sin error (AC-5-3)", () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("SecurityError: Access is denied");
    });
    expect(loadPlaybackRate()).toBe(1);

    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("QuotaExceededError");
    });
    // savePlaybackRate no debe lanzar excepción
    expect(() => savePlaybackRate(1.25)).not.toThrow();
  });
});
