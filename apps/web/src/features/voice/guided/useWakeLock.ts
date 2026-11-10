import { useEffect, useRef, useState } from "react";

export interface UseWakeLockResult {
  isSupported: boolean;
  isActive: boolean;
}

/**
 * Hook para mantener la pantalla activa durante el modo guiado mediante Screen Wake Lock API.
 * Tolerante a fallos: si la API no está soportada o lanza error, falla silenciosamente (AC-10-3).
 */
export function useWakeLock(enabled = true): UseWakeLockResult {
  const [isActive, setIsActive] = useState(false);
  const [isSupported, setIsSupported] = useState(false);
  const sentinelRef = useRef<WakeLockSentinel | null>(null);

  useEffect(() => {
    const supported =
      typeof navigator !== "undefined" && "wakeLock" in navigator && Boolean(navigator.wakeLock);
    setIsSupported(supported);

    if (!enabled || !supported) {
      return;
    }

    let isMounted = true;

    async function requestLock() {
      try {
        if (sentinelRef.current && !sentinelRef.current.released) {
          return;
        }
        const lock = await navigator.wakeLock.request("screen");
        if (!isMounted) {
          lock.release().catch(() => {});
          return;
        }
        sentinelRef.current = lock;
        setIsActive(true);

        lock.addEventListener("release", () => {
          if (sentinelRef.current === lock) {
            sentinelRef.current = null;
            setIsActive(false);
          }
        });
      } catch {
        // Silencioso según AC-10-3 (permiso denegado, batería baja, etc.)
        setIsActive(false);
      }
    }

    requestLock();

    const handleVisibilityChange = () => {
      if (document.visibilityState === "visible") {
        requestLock();
      }
    };

    document.addEventListener("visibilitychange", handleVisibilityChange);

    return () => {
      isMounted = false;
      document.removeEventListener("visibilitychange", handleVisibilityChange);
      if (sentinelRef.current) {
        sentinelRef.current.release().catch(() => {});
        sentinelRef.current = null;
      }
      setIsActive(false);
    };
  }, [enabled]);

  return { isSupported, isActive };
}
