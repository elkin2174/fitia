"""HU 1: programas académicos, usuarios, consentimientos, tokens de verificación y sesiones.

Revision ID: 0001_hu1_auth_schema
Revises:
Create Date: 2026-10-12
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_hu1_auth_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TSTZ = sa.DateTime(timezone=True)


def _uuid_pk() -> sa.Column:
    return sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()"))


def _user_fk() -> sa.Column:
    return sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS citext")

    op.create_table(
        "academic_programs",
        sa.Column("code", sa.String(20), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
    )

    op.create_table(
        "users",
        _uuid_pk(),
        sa.Column("email", postgresql.CITEXT(), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("nickname", sa.String(20), nullable=False),
        sa.Column("program_code", sa.String(20), sa.ForeignKey("academic_programs.code"), nullable=False),
        sa.Column("role", sa.Text(), nullable=False, server_default=sa.text("'student'")),
        sa.Column("email_verified_at", TSTZ, nullable=True),
        sa.Column("created_at", TSTZ, nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("email", name="users_email_key"),
        sa.CheckConstraint(r"email ~ '^[^@\s]+@correounivalle\.edu\.co$'", name="ck_users_email_domain"),
        sa.CheckConstraint("char_length(nickname) BETWEEN 3 AND 20", name="ck_users_nickname_length"),
        sa.CheckConstraint("role IN ('student', 'monitor')", name="ck_users_role"),
    )
    op.create_index("ix_users_program_code", "users", ["program_code"])

    op.create_table(
        "email_verification_tokens",
        _uuid_pk(),
        _user_fk(),
        sa.Column("token_hash", sa.Text(), nullable=False, unique=True),
        sa.Column("expires_at", TSTZ, nullable=False),
        sa.Column("used_at", TSTZ, nullable=True),
    )
    op.create_index("ix_email_verification_tokens_user_id", "email_verification_tokens", ["user_id"])

    op.create_table(
        "consents",
        _uuid_pk(),
        _user_fk(),
        sa.Column("text_version", sa.Text(), nullable=False),
        sa.Column("accepted_at", TSTZ, nullable=False),
    )
    op.create_index("ix_consents_user_id", "consents", ["user_id"])

    op.create_table(
        "sessions",
        _uuid_pk(),
        _user_fk(),
        sa.Column("token_hash", sa.Text(), nullable=False, unique=True),
        sa.Column("expires_at", TSTZ, nullable=False),
        sa.Column("last_seen_at", TSTZ, nullable=False),
    )
    op.create_index("ix_sessions_user_id", "sessions", ["user_id"])


def downgrade() -> None:
    op.drop_table("sessions")
    op.drop_table("consents")
    op.drop_table("email_verification_tokens")
    op.drop_table("users")
    op.drop_table("academic_programs")
