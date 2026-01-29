"""Situational feature computation for ML models.

Computes game context features that don't depend on team performance:
- Rest days between games
- Back-to-back detection
- Schedule density (games in recent window)
- Season progress indicators
"""

from datetime import datetime, date, timedelta
from typing import Union

from nba_betting_agent.ml.data.schema import HistoricalGame


def compute_situational_features(
    games: list[HistoricalGame],
    game_date: Union[date, datetime],
    home_team: str,
    away_team: str,
) -> dict[str, float]:
    """Compute situational features for a game.

    Uses only games BEFORE game_date (strict < comparison)
    to prevent look-ahead bias in ML training.

    Args:
        games: List of historical games to compute features from
        game_date: Date of the target game
        home_team: Home team abbreviation (e.g., "BOS")
        away_team: Away team abbreviation (e.g., "LAL")

    Returns:
        Dictionary of feature names to float values:
        - home_rest_days, away_rest_days, rest_advantage
        - home_b2b, away_b2b, b2b_disadvantage
        - home_games_last_7, away_games_last_7, schedule_density_diff
        - games_into_season, season_pct
    """
    # Convert datetime to date for comparison
    if isinstance(game_date, datetime):
        target_date = game_date.date()
    else:
        target_date = game_date

    # Filter games strictly BEFORE the target date (no leakage)
    prior_games = [
        g for g in games
        if _get_game_date(g) < target_date
    ]

    # Get team games
    home_team_games = _get_team_games(prior_games, home_team)
    away_team_games = _get_team_games(prior_games, away_team)

    features = {}

    # 1. Rest Days Features
    home_rest = _compute_rest_days(home_team_games, target_date)
    away_rest = _compute_rest_days(away_team_games, target_date)

    features["home_rest_days"] = home_rest
    features["away_rest_days"] = away_rest
    features["rest_advantage"] = home_rest - away_rest

    # 2. Back-to-Back Detection
    home_b2b = 1.0 if home_rest == 1 else 0.0
    away_b2b = 1.0 if away_rest == 1 else 0.0

    features["home_b2b"] = home_b2b
    features["away_b2b"] = away_b2b

    # b2b_disadvantage: 1.0 if home has B2B but away doesn't
    #                   -1.0 if away has B2B but home doesn't
    #                   0.0 if same situation
    if home_b2b > 0 and away_b2b == 0:
        b2b_disadvantage = 1.0
    elif away_b2b > 0 and home_b2b == 0:
        b2b_disadvantage = -1.0
    else:
        b2b_disadvantage = 0.0

    features["b2b_disadvantage"] = b2b_disadvantage

    # 3. Schedule Density (games in last 7 days)
    home_games_7 = _count_games_in_window(home_team_games, target_date, days=7)
    away_games_7 = _count_games_in_window(away_team_games, target_date, days=7)

    features["home_games_last_7"] = float(home_games_7)
    features["away_games_last_7"] = float(away_games_7)
    features["schedule_density_diff"] = float(home_games_7 - away_games_7)

    # 4. Season Progress
    # Count total games for home team as proxy for season progress
    games_played = len(home_team_games)
    features["games_into_season"] = float(min(games_played, 82))
    features["season_pct"] = min(games_played / 82.0, 1.0)

    return features


def _get_game_date(game: HistoricalGame) -> date:
    """Extract date from game, handling datetime vs date."""
    if isinstance(game.game_date, datetime):
        return game.game_date.date()
    return game.game_date


def _get_team_games(games: list[HistoricalGame], team: str) -> list[HistoricalGame]:
    """Get all games where team participated, sorted by date."""
    team_games = [
        g for g in games
        if g.home_team == team or g.away_team == team
    ]
    return sorted(team_games, key=lambda g: g.game_date)


def _compute_rest_days(team_games: list[HistoricalGame], target_date: date) -> float:
    """Compute days since team's last game.

    Returns:
        Days of rest (1-7, capped at 7). Returns 7.0 if no prior games.
    """
    if not team_games:
        return 7.0  # First game of season - treat as well-rested

    # Get most recent game (list is sorted by date)
    last_game = team_games[-1]
    last_game_date = _get_game_date(last_game)

    days_rest = (target_date - last_game_date).days

    # Cap at 7 days (all-star break, etc.)
    return float(min(max(days_rest, 0), 7))


def _count_games_in_window(
    team_games: list[HistoricalGame],
    target_date: date,
    days: int,
) -> int:
    """Count how many games team played in the last N days."""
    window_start = target_date - timedelta(days=days)

    count = 0
    for game in team_games:
        game_dt = _get_game_date(game)
        if window_start <= game_dt < target_date:
            count += 1

    return count
