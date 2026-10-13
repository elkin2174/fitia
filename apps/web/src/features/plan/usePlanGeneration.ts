import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { isApiError } from "../../shared/api/client";
import { planApi, planKey, todayKey } from "./api";

export const POLL_INTERVAL_MS = 3000;
export const SLOW_GENERATION_MS = 60_000;

export const FAILURE_MESSAGES: Record<string, string> = {
  GENERATION_TIMEOUT: "La generación tardó más de lo esperado.",
  AI_UNAVAILABLE: "El servicio de planes no está disponible ahora.",
  AI_INVALID_OUTPUT: "No pudimos armar un plan válido.",
  STALE: "La generación se interrumpió.",
};

export const failureText = (code: string) =>
  FAILURE_MESSAGES[code] ?? "No pudimos armar tu plan.";

export const ROTATING_MESSAGES = [
  "Revisando tu objetivo y tu nivel…",
  "Ajustando cada sesión a tus minutos disponibles…",
  "Eligiendo ejercicios según tu acceso a máquinas…",
  "Escribiendo una explicación breve para cada ejercicio…",
];

/** Se activa cuando una espera supera `ms`; `reset` vuelve a empezar la cuenta. */
export function useSlowFlag(active: boolean, ms: number = SLOW_GENERATION_MS) {
  const [reached, setReached] = useState(false);
  const [round, setRound] = useState(0);
  useEffect(() => {
    setReached(false);
    if (!active) return;
    const timer = window.setTimeout(() => setReached(true), ms);
    return () => window.clearTimeout(timer);
  }, [active, ms, round]);
  return { reached: active && reached, reset: () => setRound((r) => r + 1) };
}

export function usePlanGeneration() {
  const queryClient = useQueryClient();
  const generate = useMutation({
    mutationFn: planApi.generate,
    onSettled: (_data, error) => {
      if (!error || isApiError(error, "PLAN_UP_TO_DATE")) {
        void queryClient.invalidateQueries({ queryKey: planKey });
        void queryClient.invalidateQueries({ queryKey: todayKey });
      }
    },
  });

  return { generate };
}
