"""add unique constraint to historical_odds

Revision ID: 9402166567cd
Revises: e2b246866c67
Create Date: 2026-02-07 20:29:02.294878

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9402166567cd'
down_revision: Union[str, Sequence[str], None] = 'e2b246866c67'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_unique_constraint(
        "uq_odds_snapshot",
        "historical_odds",
        ["game_id", "bookmaker", "market", "outcome", "timestamp"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint("uq_odds_snapshot", "historical_odds", type_="unique")
