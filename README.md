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

## 🚀 Despliegue

* **Frontend (Vercel):** Configurado con `Root Directory: apps/web`. Los llamados a `/api/*` se redirigen transparentemente al backend sin problemas de CORS.
* **Backend (Render):** Configurado con `Root Directory: apps/api`. Gestionado automáticamente vía `render.yaml`.
* **Base de Datos (Supabase):** PostgreSQL administrado. Las conexiones pasan únicamente por el backend FastAPI.
