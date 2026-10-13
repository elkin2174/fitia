import { useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";
import { useLocation, useNavigate } from "react-router";
import { setAuthListener } from "../shared/api/client";
import { clearSession, markOnboarding } from "../shared/session/session";

/** Conecta las respuestas 401/403 del cliente HTTP con la navegación (§4.1). */
export function AuthBridge() {
  const navigate = useNavigate();
  const location = useLocation();
  const client = useQueryClient();

  useEffect(() => {
    setAuthListener((event) => {
      if (event === "unauthenticated") {
        clearSession(client);
        const back = `${window.location.pathname}${window.location.search}`;
        navigate(`/iniciar-sesion?volver=${encodeURIComponent(back)}`, { replace: true });
      } else {
        markOnboarding(client, false);
        navigate("/diagnostico", { replace: true });
      }
    });
    return () => setAuthListener(null);
  }, [client, navigate]);

  // Al cambiar de pantalla, el foco va al contenido principal (lectores de pantalla y teclado).
  useEffect(() => {
    document.getElementById("main")?.focus({ preventScroll: true });
    window.scrollTo?.(0, 0);
  }, [location.pathname]);

  return null;
}
