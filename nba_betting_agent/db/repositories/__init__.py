"""Repository layer for database access patterns.

Provides high-level interfaces for querying and storing data with
caching strategies specific to each data type.
"""

from nba_betting_agent.db.repositories.games import GamesRepository
from nba_betting_agent.db.repositories.odds import OddsRepository

__all__ = ["GamesRepository", "OddsRepository"]
