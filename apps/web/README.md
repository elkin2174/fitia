# FITIA — Frontend (HU 1 a HU 7)

SPA en React 19 + TypeScript + Vite 8, React Router 8, TanStack Query 5, React Hook Form + Zod y Tailwind 4.
Consume la API de `apps/api` en `/api/v1`. Requiere **Node 22.22 o superior**.

## Con Docker (todo el stack)

Desde la raíz del repositorio, `docker compose up --build` levanta la base de datos, la API y este frontend en
http://localhost:3000 (ver el README raíz). Es la opción más corta; las instrucciones de abajo son para correr el
frontend a mano contra un backend que ya tengas levantado.

## Correr contra el backend local

1. Backend (desde `apps/api`), con la cookie por HTTP y la IA falsa:
   ```bash
   POSTGRES_PORT=5433 docker compose up -d db          # desde la raíz del repo
   # .env del backend: COOKIE_SECURE=false, AI_PROVIDER=fake, MAIL_PROVIDER=console,
   #                   FRONTEND_BASE_URL=http://localhost:5173 (para el enlace de verificación)
   .venv/bin/alembic upgrade head && .venv/bin/python -m seeds.load_academic_programs
   .venv/bin/uvicorn app.main:app --reload --port 8000
   ```
2. Frontend (desde `apps/web`):
   ```bash
   cp .env.example .env
   npm install
   npm run dev            # http://localhost:5173
   ```

Vite reenvía `/api` a `http://localhost:8000` (`VITE_API_PROXY_TARGET`), así la cookie `fitia_session`
queda en el mismo origen que la SPA, igual que en producción con el rewrite de Vercel (ADR-04). El CORS del
backend ya admite `http://localhost:5173` por si llamas a la API directamente.

El correo de verificación sale en la consola de uvicorn (`ConsoleMailer`): abre el enlace
`http://localhost:5173/verificar-correo?token=…`.

## Scripts

| Comando | Qué hace |
|---|---|
| `npm run dev` | Servidor de desarrollo con proxy a la API |
| `npm test` | Pruebas de componentes y de flujo (Vitest + Testing Library + MSW) |
| `npm run typecheck` | Comprobación de tipos |
| `npm run build` | Tipos + build de producción en `dist/` |

## Reglas que el código garantiza

- Todas las peticiones salen del cliente único `src/shared/api/client.ts`: `credentials: "include"` siempre y
  `X-Requested-With: fitia` en toda mutación. El token de sesión nunca se lee ni se guarda en el cliente.
- La sesión es la respuesta de `GET /me` (TanStack Query). Un 401 `UNAUTHENTICATED` lleva al login con la ruta
  de retorno; un 403 `ONBOARDING_REQUIRED`, al diagnóstico.
- El diagnóstico y su edición se construyen solo con `GET /onboarding/questionnaire`, y los `code` se envían con
  su tipo JSON original.
- El plan se consulta cada 3 s solo mientras se genera, y un fallo nunca se reintenta automáticamente.
- La edición del perfil envía solo los campos que cambiaron y nunca `points`, `level`, `ranking_position` ni
  `physical_updated_at`.

## Despliegue (Vercel)

`vercel.json` reenvía `/api/*` al backend de Render y el resto de rutas a `index.html` (necesario para abrir
`/verificar-correo?token=…` desde el correo o recargar cualquier pantalla). Root Directory: `apps/web`.
