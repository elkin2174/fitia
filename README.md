# FITIA (Fit-AI) - MVP

Entrenamiento personal inteligente con Inteligencia Artificial y gamificación para estudiantes de la Universidad del Valle (Univalle - 2026).

---

## 🏛️ Arquitectura del Monorepo

```text
fitia/
├── apps/
│   ├── web/                         # React + Vite + TypeScript (Despliegue en Vercel)
│   │   ├── src/
│   │   │   ├── app/                 # Rutas, layout, guards de sesión
│   │   │   ├── features/            # auth, onboarding, profile, training, calendar, challenges
│   │   │   ├── shared/              # Componentes UI, hooks, cliente API generado
│   │   │   └── styles/              # Tailwind CSS
│   │   └── vercel.json              # Rewrites /api/* → Render
│   └── api/                         # FastAPI (Despliegue en Render)
│       ├── app/
│       │   ├── core/                # Config, DB, clock, mailer, logging, security
│       │   ├── modules/             # auth, onboarding, profile, training, calendar, challenges
│       │   └── ai/                  # Puertos y adaptadores (Gemini, FakeAdapter, etc.)
│       ├── prompts/                 # Prompts versionados en YAML
│       ├── migrations/              # Alembic (Postgres / Supabase)
│       └── seeds/                   # Semillas de bodega, ejercicios, festivos y programas
├── docs/                            # Arquitectura, ADRs y trazabilidad HU
├── docker-compose.yml               # Entorno local (Postgres + API + Web)
└── .github/workflows/               # CI/CD workflows
```

---

## 🐳 Desarrollo local con Docker

Un solo comando levanta la base de datos, la API y el frontend:

```bash
cp .env.example .env          # opcional: todo tiene valores por defecto
docker compose up --build
```

| Servicio | URL en el equipo | Notas |
|---|---|---|
| Frontend (Vite, recarga en caliente) | http://localhost:3000 | Reenvía `/api` a la API: la cookie de sesión queda en el mismo origen. |
| API (FastAPI, recarga en caliente) | http://localhost:8000/docs | Al arrancar aplica las migraciones y carga los programas académicos (idempotente). |
| PostgreSQL 16 | `localhost:5433` (usuario/clave `postgres`, base `fitia_db`) | Solo en `127.0.0.1`. Los datos persisten en el volumen `postgres_data`. |

- **Puertos:** cambia `POSTGRES_PORT`, `API_PORT` o `WEB_PORT` en `.env` si alguno está ocupado. Si tienes un Postgres instalado en el equipo (5432) no hay conflicto: el de Docker usa 5433.
- **Correo de verificación:** se imprime en los logs de la API (`docker compose logs -f api`); copia el enlace.
- **IA del plan:** por defecto `AI_PROVIDER=fake` (sin clave). Para Gemini real, define `AI_PROVIDER=gemini` y `GEMINI_API_KEY` en `.env` y reinicia la API.
- **Pruebas dentro de los contenedores:**
  ```bash
  docker compose exec api pytest -q      # usa la base fitia_test, nunca la de desarrollo
  docker compose exec web npm test
  ```
- **Cambios en dependencias** (`requirements.txt` o `package.json`): `docker compose up --build`.
- **Reiniciar desde cero** (borra la base de datos): `docker compose down -v`.
- **Ver la base de datos:** `docker compose exec db psql -U postgres -d fitia_db`.

---

## 🚀 Despliegue

* **Frontend (Vercel):** Configurado con `Root Directory: apps/web`. Los llamados a `/api/*` se redirigen transparentemente al backend sin problemas de CORS.
* **Backend (Render):** Configurado con `Root Directory: apps/api`. Gestionado automáticamente vía `render.yaml`.
* **Base de Datos (Supabase):** PostgreSQL administrado. Las conexiones pasan únicamente por el backend FastAPI.
