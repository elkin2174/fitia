import { useMutation } from "@tanstack/react-query";
import { useNavigate } from "react-router";
import { isApiError } from "../../shared/api/client";
import { useSessionActions } from "../../shared/session/session";
import { useToast } from "../../shared/ui/Toast";
import { authApi } from "./api";

/** Cierra la sesión en el servidor. Un 401 significa que ya estaba cerrada: se continúa igual. */
export function useLogout() {
  const navigate = useNavigate();
  const session = useSessionActions();
  const toast = useToast();
  return useMutation({
    mutationFn: async () => {
      try {
        await authApi.logout();
      } catch (error) {
        if (!(isApiError(error) && error.status === 401)) throw error;
      }
    },
    onSuccess: () => {
      session.clear("logged_out");
      void navigate("/", { replace: true, state: { notice: "logged_out" } });
    },
    onError: (error) => toast(error.message, "danger"),
  });
}
