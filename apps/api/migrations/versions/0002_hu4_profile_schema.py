"""HU 4: perfil con las respuestas del diagnóstico inicial y días de entrenamiento.

Revision ID: 0002_hu4_profile_schema
Revises: 0001_hu1_auth_schema
Create Date: 2026-10-12

Los valores de los CHECK se escriben literales a propósito (una migración no debe depender de
código de la app que puede cambiar). Deben coincidir con app/modules/profile/options.py;
tests/integration/test_profile_schema.py lo verifica.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_hu4_profile_schema"
down_revision: str | None = "0001_hu1_auth_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TSTZ = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table(
        "profiles",
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("goal", sa.Text(), nullable=False),
        sa.Column("term_weeks", sa.SmallInteger(), nullable=False),
        sa.Column("fitness_level", sa.Text(), nullable=False),
        sa.Column("session_minutes", sa.SmallInteger(), nullable=False),
        sa.Column("has_machine_access", sa.Boolean(), nullable=False),
        sa.Column("created_at", TSTZ, nullable=False),
        sa.Column("updated_at", TSTZ, nullable=False),
        sa.CheckConstraint(
            "goal IN ('general_health', 'strength', 'endurance', 'weight_loss')", name="ck_profiles_goal"
        ),
        sa.CheckConstraint(
            "fitness_level IN ('beginner', 'intermediate', 'advanced')", name="ck_profiles_fitness_level"
        ),
        sa.CheckConstraint("term_weeks IN (4, 8, 12)", name="ck_profiles_term_weeks"),
        sa.CheckConstraint("session_minutes IN (15, 30, 45, 60)", name="ck_profiles_session_minutes"),
    )

    op.create_table(
        "profile_training_days",
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("weekday", sa.SmallInteger(), nullable=False),
        sa.PrimaryKeyConstraint("user_id", "weekday"),
        sa.CheckConstraint("weekday BETWEEN 1 AND 5", name="ck_profile_training_days_weekday"),
    )


def downgrade() -> None:
    op.drop_table("profile_training_days")
    op.drop_table("profiles")
