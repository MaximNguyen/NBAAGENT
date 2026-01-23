"""Pydantic models for NBA team statistics and injury data.

Models match the state contract from 03-CONTEXT.md and provide validation
for percentage fields, ratings, and other statistical values.
"""

from datetime import datetime

from pydantic import BaseModel, field_validator


class TeamRecord(BaseModel):
    """Win/loss record.

    Attributes:
        wins: Number of wins
        losses: Number of losses
    """

    wins: int
    losses: int


class TeamBasicStats(BaseModel):
    """Basic per-game statistics.

    Attributes:
        pts: Points per game
        reb: Rebounds per game
        ast: Assists per game
        stl: Steals per game (optional)
        blk: Blocks per game (optional)
        tov: Turnovers per game (optional)
        fg_pct: Field goal percentage (0.0-1.0)
        fg3_pct: Three-point percentage (0.0-1.0)
        ft_pct: Free throw percentage (0.0-1.0)
    """

    pts: float
    reb: float
    ast: float
    stl: float = 0.0
    blk: float = 0.0
    tov: float = 0.0
    fg_pct: float
    fg3_pct: float
    ft_pct: float

    @field_validator("fg_pct", "fg3_pct", "ft_pct")
    @classmethod
    def validate_percentage(cls, v: float, info) -> float:
        """Validate percentage fields are between 0.0 and 1.0.

        Args:
            v: Percentage value
            info: Field info from Pydantic

        Returns:
            Validated percentage

        Raises:
            ValueError: If percentage is outside valid range
        """
        if not 0.0 <= v <= 1.0:
            raise ValueError(
                f"{info.field_name} must be between 0.0 and 1.0, got {v}"
            )
        return v


class TeamAdvancedMetrics(BaseModel):
    """Advanced team metrics from TeamEstimatedMetrics.

    Attributes:
        off_rtg: Offensive rating (points per 100 possessions)
        def_rtg: Defensive rating (points allowed per 100 possessions)
        net_rtg: Net rating (off_rtg - def_rtg)
        pace: Possessions per 48 minutes
        efg_pct: Effective field goal percentage (adjusts for 3-pt value)
    """

    off_rtg: float
    def_rtg: float
    net_rtg: float
    pace: float
    efg_pct: float

    @field_validator("off_rtg", "def_rtg")
    @classmethod
    def validate_rating(cls, v: float, info) -> float:
        """Validate offensive/defensive ratings are positive.

        Typical NBA ratings range from 90-130, but we allow any positive value
        to avoid false rejections of edge cases.

        Args:
            v: Rating value
            info: Field info from Pydantic

        Returns:
            Validated rating

        Raises:
            ValueError: If rating is not positive
        """
        if v <= 0:
            raise ValueError(f"{info.field_name} must be positive, got {v}")
        return v

    @field_validator("efg_pct")
    @classmethod
    def validate_efg_pct(cls, v: float) -> float:
        """Validate eFG% is between 0.0 and 1.0.

        Args:
            v: eFG% value

        Returns:
            Validated eFG%

        Raises:
            ValueError: If eFG% is outside valid range
        """
        if not 0.0 <= v <= 1.0:
            raise ValueError(f"efg_pct must be between 0.0 and 1.0, got {v}")
        return v


class HomeAwayRecord(BaseModel):
    """Record and scoring for home or away games.

    Attributes:
        wins: Wins in this split
        losses: Losses in this split
        pts: Average points in this split
    """

    wins: int
    losses: int
    pts: float


class HomeAwayStats(BaseModel):
    """Home/away situational splits.

    Attributes:
        home: Home game statistics
        away: Away game statistics
    """

    home: HomeAwayRecord
    away: HomeAwayRecord


class Last10Stats(BaseModel):
    """Recent form over last 10 games.

    Attributes:
        record: Win-loss record in "W-L" format (e.g., "7-3")
        pts: Average points over last 10 games
        net_rtg: Net rating over last 10 games (optional)
    """

    record: str
    pts: float
    net_rtg: float | None = None


class TeamStats(BaseModel):
    """Complete team statistics structure.

    This is the main model for team data, containing all stats and metadata.

    Attributes:
        team_id: NBA official team ID (10-digit format like "1610612738")
        name: Full team name (e.g., "Boston Celtics")
        abbreviation: Team abbreviation (e.g., "BOS")
        record: Season win/loss record
        stats: Basic per-game statistics
        advanced: Advanced metrics (optional)
        home_away: Home/away splits (optional)
        last_10: Recent 10-game form (optional)
        fetched_at: Timestamp when data was fetched
        is_stale: Whether cache data is stale but still usable
    """

    team_id: str
    name: str
    abbreviation: str
    record: TeamRecord
    stats: TeamBasicStats
    advanced: TeamAdvancedMetrics | None = None
    home_away: HomeAwayStats | None = None
    last_10: Last10Stats | None = None
    fetched_at: datetime
    is_stale: bool = False


class InjuryReport(BaseModel):
    """Single injury report entry.

    Attributes:
        team: Team abbreviation (e.g., "BOS")
        player: Player display name
        position: Player position (e.g., "SG", "PF") - optional
        status: Injury status ("Out", "Questionable", "Day-To-Day", "Probable")
        injury: Injury type (e.g., "Ankle", "Knee")
        details: Additional context (optional)
        fetched_at: Timestamp when injury data was fetched
    """

    team: str
    player: str
    position: str | None = None
    status: str
    injury: str
    details: str | None = None
    fetched_at: datetime


class TeamStatsCollection(BaseModel):
    """Container for all team statistics keyed by abbreviation.

    Attributes:
        teams: Dictionary mapping team abbreviation to TeamStats
    """

    teams: dict[str, TeamStats]

    def get_team(self, abbr: str) -> TeamStats | None:
        """Get team stats by abbreviation (case-insensitive).

        Args:
            abbr: Team abbreviation (e.g., "BOS", "bos")

        Returns:
            TeamStats if found, None otherwise
        """
        return self.teams.get(abbr.upper())
