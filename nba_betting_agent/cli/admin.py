"""CLI command to promote a user to admin role.

Usage:
    python -m nba_betting_agent.cli.admin promote user@example.com
"""

import sys

from sqlalchemy import create_engine, select, update
from sqlalchemy.orm import Session

from nba_betting_agent.db.models import UserModel


def get_sync_database_url() -> str:
    """Get a synchronous database URL for CLI usage."""
    import os

    db_url = os.getenv("DATABASE_URL")

    if db_url:
        if db_url.startswith("postgres://"):
            db_url = db_url.replace("postgres://", "postgresql://", 1)
        # Strip async driver for sync access
        db_url = db_url.replace("postgresql+asyncpg://", "postgresql://")
        return db_url

    return "sqlite:///./nba_betting.db"


def promote(email: str) -> None:
    """Promote a user to admin by email."""
    engine = create_engine(get_sync_database_url())

    with Session(engine) as session:
        result = session.execute(select(UserModel).where(UserModel.email == email.lower().strip()))
        user = result.scalar_one_or_none()

        if not user:
            print(f"Error: No user found with email '{email}'")
            sys.exit(1)

        if user.role == "admin":
            print(f"User '{email}' is already an admin.")
            return

        user.role = "admin"
        session.commit()
        print(f"User '{email}' promoted to admin.")


def main():
    if len(sys.argv) < 3 or sys.argv[1] != "promote":
        print("Usage: python -m nba_betting_agent.cli.admin promote <email>")
        sys.exit(1)

    promote(sys.argv[2])


if __name__ == "__main__":
    main()
