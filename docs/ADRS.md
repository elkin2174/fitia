# Registro de Decisiones de Arquitectura (ADRs) - FITIA

| ID | Decisión | Alternativas | Justificación | Consecuencias |
| :--- | :--- | :--- | :--- | :--- |
| **ADR-01** | Monolito modular FastAPI (`routers` → `services` → `repositories`) | Microservicios; funciones serverless | Equipo ágil y 2 sprints; reglas transversales; menor costo de coordinación. | Un solo despliegue. Requiere disciplina de módulos. |
| **ADR-02** | Supabase solo como Postgres administrado (sin PostgREST ni Auth en cliente) | Supabase como BaaS completo | Mantiene la lógica de negocio y secretos de IA en servidor. | Conexión por pooler y migraciones por conexión directa. |
| **ADR-03** | Autenticación propia con sesiones en servidor (token opaco, hash en BD, cookie `HttpOnly`, contraseñas Argon2id) | JWT sin estado; Supabase Auth | Validación atómica de dominio institucional y baja inmediata de sesión (AC-3-1). | Consulta a BD por request autenticado. |
| **ADR-04** | Mismo origen mediante rewrite de Vercel hacia Render (`/api/*`) | Cookies cross-site (`SameSite=None`); JWT en localStorage | Evita bloqueo de cookies de terceros (Safari/móvil) y elimina problemas de CORS. | Mantiene regla de rewrite por entorno. |
| **ADR-05** | SQLAlchemy 2 + Alembic + Pydantic v2 | SQL crudo; Prisma | Estándar del ecosistema FastAPI; migraciones versionadas; validación en el borde. | Tipado estricto en BD y schemas. |
| **ADR-06** | Bodega (rutinas, ejercicios, guías, programas, festivos) en BD por seeds JSON/YAML | Constantes en código | Seeds auditables por PR y verificables contra criterios de aceptación. | Contenido publicado con migraciones/seeds. |
| **ADR-07** | IA detrás de puertos por modalidad con prompts versionados en YAML | Llamadas directas al SDK desde servicios | Extensibilidad a audio/visión y pruebas con adaptador falso (`FakeTextAdapter`). | Capa limpia desacoplada del proveedor de LLM. |
| **ADR-08** | Enlace de correo abre pantalla del front que hace `POST /auth/verify-email` | `GET` directo desde el enlace | Evita que escáneres automáticos de correo institucional consuman el token. | Flujo de activación seguro. |
| **ADR-09** | Parámetros de "sesión de hoy" (tiempo y máquinas) viajan como query params | Persistirlos en servidor | HU 9 exige no alterar el perfil base del usuario. | Estado efímero en cliente. |
| **ADR-10** | Zona horaria única `America/Bogota` y reloj inyectable | UTC con conversión | Público universitario local; simplifica cortes de día, rachas y festivos. | Pruebas deterministas de tiempo. |
| **ADR-11** | Frontend: React + Vite + TypeScript, React Router, TanStack Query, React Hook Form + Zod, Tailwind | Next.js; Redux | SPA rápida; TanStack Query evita estado global complejo. | Renderizado fluido en cliente. |
| **ADR-12** | Correo transaccional mediante API HTTP con SPF/DKIM | SMTP personal | Máxima entregabilidad hacia cuentas `@correounivalle.edu.co`. | Configuración de dominio remitente. |
| **ADR-13** | API versionada `/api/v1` con OpenAPI y cliente TypeScript generado | Contratos manuales | Evita desalineación entre desarrollo frontend y backend. | Cliente generado sincronizado con Swagger. |
