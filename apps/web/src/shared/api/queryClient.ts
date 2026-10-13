import { QueryClient } from "@tanstack/react-query";
import { NETWORK_ERROR, isApiError } from "./client";

export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        // Solo se reintenta una caída de red; un error de la API es una respuesta definitiva.
        retry: (failureCount, error) => isApiError(error, NETWORK_ERROR) && failureCount < 1,
        refetchOnWindowFocus: false,
        staleTime: 30_000,
      },
      mutations: { retry: false },
    },
  });
}
