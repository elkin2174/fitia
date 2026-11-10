export type PlaybackRate = 0.75 | 1 | 1.25;

export const PLAYBACK_RATES: readonly PlaybackRate[] = [0.75, 1, 1.25] as const;

export const DEFAULT_PLAYBACK_RATE: PlaybackRate = 1;

export const PLAYBACK_RATE_STORAGE_KEY = "fitia_playback_rate";

export function isPlaybackRate(value: unknown): value is PlaybackRate {
  return value === 0.75 || value === 1 || value === 1.25;
}

export function loadPlaybackRate(): PlaybackRate {
  try {
    if (typeof window === "undefined" || !window.localStorage) {
      return DEFAULT_PLAYBACK_RATE;
    }
    const raw = window.localStorage.getItem(PLAYBACK_RATE_STORAGE_KEY);
    if (!raw) return DEFAULT_PLAYBACK_RATE;
    const num = Number(raw);
    return isPlaybackRate(num) ? num : DEFAULT_PLAYBACK_RATE;
  } catch {
    return DEFAULT_PLAYBACK_RATE;
  }
}

export function savePlaybackRate(rate: PlaybackRate): void {
  try {
    if (typeof window === "undefined" || !window.localStorage) {
      return;
    }
    if (isPlaybackRate(rate)) {
      window.localStorage.setItem(PLAYBACK_RATE_STORAGE_KEY, String(rate));
    }
  } catch {
    // Si localStorage no está disponible o falla (e.g. modo incógnito, cuota), se ignora silenciosamente (AC-5-3)
  }
}
