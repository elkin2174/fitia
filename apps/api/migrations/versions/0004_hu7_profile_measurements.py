"""HU 7: peso, estatura, historial fisico y visibilidad en ranking publico.

Revision ID: 0004_hu7_profile_measurements
Revises: 0003_hu5_plan_schema
Create Date: 2026-10-12

Valores literales en CHECK a proposito (la migracion no importa codigo de la app).
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_hu7_profile_measurements"
down_revision: str | None = "0003_hu5_plan_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TSTZ = sa.DateTime(timezone=True)


def upgrade() -> None:
    # 1. Nuevas columnas y restricciones en profiles
    op.add_column("profiles", sa.Column("weight_kg", sa.Float(), nullable=True))
    op.add_column("profiles", sa.Column("height_cm", sa.Float(), nullable=True))
    op.add_column("profiles", sa.Column("physical_updated_at", TSTZ, nullable=True))
    op.add_column(
        "profiles",
        sa.Column("is_public_ranking", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )
    op.add_column(
        "profiles",
        sa.Column("points", sa.Integer(), nullable=False, server_default=sa.text("0")),
    )
    op.add_column(
        "profiles",
        sa.Column("level", sa.Integer(), nullable=False, server_default=sa.text("1")),
    )

    op.create_check_constraint(
        "ck_profiles_weight_range",
        "profiles",
        "weight_kg IS NULL OR (weight_kg >= 20.0 AND weight_kg <= 400.0)",
    )
    op.create_check_constraint(
        "ck_profiles_height_range",
        "profiles",
        "height_cm IS NULL OR (height_cm >= 50.0 AND height_cm <= 270.0)",
    )
    op.create_check_constraint(
        "ck_profiles_points",
        "profiles",
        "points >= 0",
    )
    op.create_check_constraint(
        "ck_profiles_level",
        "profiles",
        "level >= 1",
    )

    # 2. Tabla de historial fisico inmutable
    op.create_table(
        "physical_measurements",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("weight_kg", sa.Float(), nullable=True),
        sa.Column("height_cm", sa.Float(), nullable=True),
        sa.Column("recorded_at", TSTZ, nullable=False),
        sa.CheckConstraint(
            "weight_kg IS NULL OR (weight_kg >= 20.0 AND weight_kg <= 400.0)",
            name="ck_physical_measurements_weight",
        ),
        sa.CheckConstraint(
            "height_cm IS NULL OR (height_cm >= 50.0 AND height_cm <= 270.0)",
            name="ck_physical_measurements_height",
        ),
        sa.CheckConstraint(
            "weight_kg IS NOT NULL OR height_cm IS NOT NULL",
            name="ck_physical_measurements_has_value",
        ),
    )

    op.create_index(
        "ix_physical_measurements_user_recorded",
        "physical_measurements",
        ["user_id", "recorded_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_physical_measurements_user_recorded", table_name="physical_measurements")
    op.drop_table("physical_measurements")

    op.drop_constraint("ck_profiles_level", "profiles", type_="check")
    op.drop_constraint("ck_profiles_points", "profiles", type_="check")
    op.drop_constraint("ck_profiles_height_range", "profiles", type_="check")
    op.drop_constraint("ck_profiles_weight_range", "profiles", type_="check")

    op.drop_column("profiles", "level")
    op.drop_column("profiles", "points")
    op.drop_column("profiles", "is_public_ranking")
    op.drop_column("profiles", "physical_updated_at")
    op.drop_column("profiles", "height_cm")
    op.drop_column("profiles", "weight_kg")
