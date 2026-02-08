"""add role column and audit_log table

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-02-08 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add role column to users table and create audit_log table."""
    op.add_column("users", sa.Column("role", sa.String(20), nullable=False, server_default="user"))

    op.create_table(
        "audit_log",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
        sa.Column("admin_id", sa.String(36), nullable=False),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("target_id", sa.String(36), nullable=True),
        sa.Column("details", sa.Text(), nullable=True),
    )
    op.create_index("ix_audit_log_timestamp", "audit_log", ["timestamp"])


def downgrade() -> None:
    """Remove audit_log table and role column."""
    op.drop_index("ix_audit_log_timestamp", table_name="audit_log")
    op.drop_table("audit_log")
    op.drop_column("users", "role")
