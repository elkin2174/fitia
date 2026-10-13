"""NFR-12 / AC-3-5: garantía de esquema para que eliminar una cuenta nunca deje restos.

Toda tabla con datos de un usuario (HU futuras incluidas) debe colgar de `users` con ON DELETE CASCADE.
Si una migración nueva lo olvida, estas pruebas fallan en CI.
"""
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# Tablas con columna `user_id` que, justificadamente, no cuelgan de users con CASCADE.
# Hoy no hay ninguna (`ai_call_logs` no tendrá `user_id` por diseño). Toda entrada nueva debe
# llevar su justificación en un comentario y aprobarse en revisión.
CASCADE_EXCEPTIONS: dict[str, str] = {}

FKS_TO_USERS = text(
    """
    SELECT c.conrelid::regclass::text AS table_name, c.conname, c.confdeltype::text AS on_delete
    FROM pg_constraint c
    WHERE c.contype = 'f' AND c.confrelid = 'public.users'::regclass
    ORDER BY 1, 2
    """
)

USER_ID_TABLES_WITHOUT_CASCADE = text(
    """
    SELECT cols.table_name
    FROM information_schema.columns cols
    WHERE cols.table_schema = 'public'
      AND cols.column_name = 'user_id'
      AND NOT EXISTS (
          SELECT 1
          FROM pg_constraint c
          JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = ANY (c.conkey)
          WHERE c.contype = 'f'
            AND c.conrelid = format('%I.%I', cols.table_schema, cols.table_name)::regclass
            AND c.confrelid = 'public.users'::regclass
            AND c.confdeltype = 'c'
            AND a.attname = 'user_id'
      )
    ORDER BY 1
    """
)


async def test_toda_fk_hacia_users_es_on_delete_cascade(db: AsyncSession) -> None:
    rows = (await db.execute(FKS_TO_USERS)).all()

    assert {r.table_name for r in rows} >= {"sessions", "consents", "email_verification_tokens"}
    offenders = [f"{r.table_name}.{r.conname} (confdeltype={r.on_delete})" for r in rows if r.on_delete != "c"]
    assert offenders == [], f"FK hacia users sin ON DELETE CASCADE: {offenders}"


async def test_toda_tabla_con_user_id_cuelga_de_users_con_cascade(db: AsyncSession) -> None:
    tables = (await db.scalars(USER_ID_TABLES_WITHOUT_CASCADE)).all()

    offenders = [t for t in tables if t not in CASCADE_EXCEPTIONS]
    assert offenders == [], f"Tablas con user_id sin FK CASCADE a users: {offenders}"


async def test_la_verificacion_de_esquema_detecta_una_tabla_sin_cascade(db: AsyncSession) -> None:
    """Autochequeo: una tabla nueva sin CASCADE debe ser detectada (se revierte al final)."""
    await db.execute(
        text("CREATE TABLE tmp_sin_cascade (id serial PRIMARY KEY, user_id uuid REFERENCES users (id))")
    )
    await db.execute(text("CREATE TABLE tmp_sin_fk (id serial PRIMARY KEY, user_id uuid)"))
    try:
        fks = (await db.execute(FKS_TO_USERS)).all()
        tables = (await db.scalars(USER_ID_TABLES_WITHOUT_CASCADE)).all()
    finally:
        await db.rollback()

    assert any(r.table_name == "tmp_sin_cascade" and r.on_delete != "c" for r in fks)
    assert set(tables) == {"tmp_sin_cascade", "tmp_sin_fk"}
