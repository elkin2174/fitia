# Migraciones con Alembic

Control de versiones del esquema de base de datos PostgreSQL (Supabase) con SQLAlchemy 2 (ADR-05).
- Conexión directa a Supabase para correr migraciones: `alembic upgrade head`.
- Migraciones ejecutadas automáticamente en el pipeline de CI/CD antes del despliegue en Render.
