"""HU 5: plan semanal generado por IA (planes, días, ejercicios) y métricas de llamadas a la IA.

Revision ID: 0003_hu5_plan_schema
Revises: 0002_hu4_profile_schema
Create Date: 2026-10-12

Valores literales a propósito (la migración no importa código de la app). Deben coincidir con
app/modules/plan/models.py, app/ai/call_log.py y app/ai/use_cases/weekly_plan/rules.py;
tests/integration/test_plan_schema.py lo verifica.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003_hu5_plan_schema"
down_revision: str | None = "0002_hu4_profile_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TSTZ = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table(
        "weekly_plans",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("week_start", sa.Date(), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("generation_number", sa.SmallInteger(), nullable=False),
        sa.Column("profile_snapshot", postgresql.JSONB(), nullable=False),
        sa.Column("prompt_version", sa.Text(), nullable=True),
        sa.Column("failure_code", sa.Text(), nullable=True),
        sa.Column("created_at", TSTZ, nullable=False),
        sa.Column("ready_at", TSTZ, nullable=True),
        sa.CheckConstraint("status IN ('generating', 'ready', 'failed')", name="ck_weekly_plans_status"),
        sa.CheckConstraint("extract(isodow FROM week_start) = 1", name="ck_weekly_plans_week_start_monday"),
        sa.CheckConstraint("start_date BETWEEN week_start AND week_start + 4", name="ck_weekly_plans_start_date"),
        sa.CheckConstraint("generation_number >= 1", name="ck_weekly_plans_generation_number"),
        sa.CheckConstraint(
            "(status = 'failed') = (failure_code IS NOT NULL)", name="ck_weekly_plans_failure_iff_failed"
        ),
        sa.CheckConstraint(
            "failure_code IS NULL OR failure_code IN "
            "('AI_UNAVAILABLE', 'AI_INVALID_OUTPUT', 'GENERATION_TIMEOUT', 'STALE')",
            name="ck_weekly_plans_failure_code",
        ),
        sa.CheckConstraint("(status = 'ready') = (ready_at IS NOT NULL)", name="ck_weekly_plans_ready_iff_ready_at"),
    )
    op.create_index("ix_weekly_plans_user_week", "weekly_plans", ["user_id", "week_start"])
    # Un plan vigente por usuario y semana; una generación en curso por usuario (NFR-23).
    op.create_index(
        "uq_weekly_plans_ready",
        "weekly_plans",
        ["user_id", "week_start"],
        unique=True,
        postgresql_where=sa.text("status = 'ready'"),
    )
    op.create_index(
        "uq_weekly_plans_generating",
        "weekly_plans",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("status = 'generating'"),
    )

    op.create_table(
        "plan_days",
        sa.Column("plan_id", sa.Uuid(), sa.ForeignKey("weekly_plans.id", ondelete="CASCADE"), nullable=False),
        sa.Column("plan_date", sa.Date(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("estimated_minutes", sa.SmallInteger(), nullable=False),
        sa.PrimaryKeyConstraint("plan_id", "plan_date"),
        sa.CheckConstraint("extract(isodow FROM plan_date) BETWEEN 1 AND 5", name="ck_plan_days_weekday"),
        sa.CheckConstraint("char_length(title) BETWEEN 1 AND 60", name="ck_plan_days_title"),
        sa.CheckConstraint("estimated_minutes BETWEEN 1 AND 60", name="ck_plan_days_estimated_minutes"),
    )

    op.create_table(
        "plan_exercises",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("plan_id", sa.Uuid(), nullable=False),
        sa.Column("plan_date", sa.Date(), nullable=False),
        sa.Column("position", sa.SmallInteger(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("sets", sa.SmallInteger(), nullable=False),
        sa.Column("reps", sa.SmallInteger(), nullable=True),
        sa.Column("work_seconds", sa.SmallInteger(), nullable=True),
        sa.Column("rest_seconds", sa.SmallInteger(), nullable=False),
        sa.Column("requires_machine", sa.Boolean(), nullable=False),
        sa.Column("steps", postgresql.JSONB(), nullable=False),
        sa.ForeignKeyConstraint(
            ["plan_id", "plan_date"],
            ["plan_days.plan_id", "plan_days.plan_date"],
            ondelete="CASCADE",
            name="fk_plan_exercises_plan_day",
        ),
        sa.UniqueConstraint("plan_id", "plan_date", "position", name="uq_plan_exercises_position"),
        sa.CheckConstraint("position >= 1", name="ck_plan_exercises_position"),
        sa.CheckConstraint("char_length(name) BETWEEN 1 AND 80", name="ck_plan_exercises_name"),
        sa.CheckConstraint("sets BETWEEN 1 AND 6", name="ck_plan_exercises_sets"),
        sa.CheckConstraint("reps IS NULL OR reps BETWEEN 1 AND 30", name="ck_plan_exercises_reps"),
        sa.CheckConstraint(
            "work_seconds IS NULL OR work_seconds BETWEEN 10 AND 120", name="ck_plan_exercises_work_seconds"
        ),
        sa.CheckConstraint("rest_seconds BETWEEN 15 AND 180", name="ck_plan_exercises_rest_seconds"),
        sa.CheckConstraint("num_nonnulls(reps, work_seconds) = 1", name="ck_plan_exercises_reps_xor_work"),
        sa.CheckConstraint(
            "CASE WHEN jsonb_typeof(steps) = 'array' THEN jsonb_array_length(steps) BETWEEN 2 AND 4 ELSE false END",
            name="ck_plan_exercises_steps",
        ),
    )

    # Métricas de la IA: sin user_id y sin contenido (ni prompt ni respuesta), por diseño (ADR-07).
    op.create_table(
        "ai_call_logs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("use_case", sa.Text(), nullable=False),
        sa.Column("prompt_version", sa.Text(), nullable=False),
        sa.Column("model", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("attempts", sa.SmallInteger(), nullable=False),
        sa.Column("created_at", TSTZ, nullable=False),
        sa.CheckConstraint(
            "status IN ('ok', 'invalid_output', 'timeout', 'provider_error', 'breaker_open', 'disabled')",
            name="ck_ai_call_logs_status",
        ),
    )


def downgrade() -> None:
    op.drop_table("ai_call_logs")
    op.drop_table("plan_exercises")
    op.drop_table("plan_days")
    op.drop_index("uq_weekly_plans_generating", table_name="weekly_plans")
    op.drop_index("uq_weekly_plans_ready", table_name="weekly_plans")
    op.drop_index("ix_weekly_plans_user_week", table_name="weekly_plans")
    op.drop_table("weekly_plans")
