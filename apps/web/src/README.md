# Estructura de `src/`

- `app/`: rutas (`routes.tsx`, carga por pantalla), guards de sesión (`guards.tsx`), layout con navegación
  inferior y `AuthBridge` (conecta los 401/403 del cliente HTTP con el router).
- `features/`
  - `auth/`: registro, revisar correo, verificación (un solo POST, también en StrictMode), login, reenvío y logout.
  - `onboarding/`: diagnóstico paso a paso construido desde el cuestionario de la API.
  - `plan/`: pantalla de inicio con la semana en carriles y el sondeo de la generación.
  - `profile/`: perfil (diagnóstico, datos físicos, privacidad, cuenta), historial y eliminación de cuenta.
    `types.ts` solo contiene tipos: las opciones salen de la API.
  - `ranking/`: ranking público.
  - `welcome/`: bienvenida y 404.
- `shared/`
  - `api/`: cliente HTTP único, tipos de los contratos y `QueryClient`.
  - `session/`: estado de sesión basado en `GET /me`.
  - `ui/`: sistema de componentes (botones, campos, selector con búsqueda, tarjetas de opción, chips de días,
    interruptor, banner, toast, diálogo, progreso, esqueletos, estado vacío, navegación inferior).
  - `lib/`: fechas en America/Bogota, `Retry-After` en lenguaje humano y mensajes por campo.
- `styles/`: tokens de diseño (claro y oscuro) y Tailwind.
- `test/`: MSW, fixtures con los contratos reales y pruebas de flujo.
