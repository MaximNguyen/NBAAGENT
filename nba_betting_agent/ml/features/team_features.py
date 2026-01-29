"""Team-level feature computation for ML models.

Computes performance features from historical game data:
- Net rating differential (points for - points against)
- Pace features (game tempo)
- Form features (recent win percentage)
- Home/away splits
"""

from datetime import datetime, date
from typing import Union

from nba_betting_agent.ml.data.schema import HistoricalGame


def compute_team_features(
    games: list[HistoricalGame],
    game_date: Union[date, datetime],
    home_team: str,
    away_team: str,
    lookback_games: int = 10,
) -> dict[str, float]:
    """Compute team-level features from historical game data.

    CRITICAL: Uses only games BEFORE game_date (strict < comparison)
    to prevent look-ahead bias in ML training.

    Args:
        games: List of historical games to compute features from
        game_date: Date of the target game (features use only earlier games)
        home_team: Home team abbreviation (e.g., "BOS")
        away_team: Away team abbreviation (e.g., "LAL")
        lookback_games: Number of recent games to use for rolling stats

    Returns:
        Dictionary of feature names to float values:
        - home_net_rtg_l{n}, away_net_rtg_l{n}, net_rtg_diff
        - home_pace_l{n}, away_pace_l{n}, pace_diff
        - home_win_pct_l10, away_win_pct_l10, form_diff
        - home_team_home_record, away_team_away_record
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

    # Get team games (where team was either home or away)
    home_team_games = _get_team_games(prior_games, home_team)
    away_team_games = _get_team_games(prior_games, away_team)

    # Compute features
    features = {}

    # 1. Net Rating Features (using lookback window)
    home_recent = home_team_games[-lookback_games:] if home_team_games else []
    away_recent = away_team_games[-lookback_games:] if away_team_games else []

    home_net_rtg = _compute_net_rating(home_recent, home_team)
    away_net_rtg = _compute_net_rating(away_recent, away_team)

    features[f"home_net_rtg_l{lookback_games}"] = home_net_rtg
    features[f"away_net_rtg_l{lookback_games}"] = away_net_rtg
    features["net_rtg_diff"] = home_net_rtg - away_net_rtg

    # 2. Pace Features (average total points)
    home_pace = _compute_pace(home_recent)
    away_pace = _compute_pace(away_recent)

    features[f"home_pace_l{lookback_games}"] = home_pace
    features[f"away_pace_l{lookback_games}"] = away_pace
    features["pace_diff"] = home_pace - away_pace

    # 3. Form Features (win percentage in last 10)
    home_win_pct = _compute_win_pct(home_recent, home_team)
    away_win_pct = _compute_win_pct(away_recent, away_team)

    features["home_win_pct_l10"] = home_win_pct
    features["away_win_pct_l10"] = away_win_pct
    features["form_diff"] = home_win_pct - away_win_pct

    # 4. Home/Away Splits (season-long home/away record)
    home_home_games = _get_home_games(prior_games, home_team)
    away_away_games = _get_away_games(prior_games, away_team)

    features["home_team_home_record"] = _compute_home_win_pct(home_home_games, home_team)
    features["away_team_away_record"] = _compute_away_win_pct(away_away_games, away_team)

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


def _get_home_games(games: list[HistoricalGame], team: str) -> list[HistoricalGame]:
    """Get all games where team played at home."""
    return [g for g in games if g.home_team == team]


def _get_away_games(games: list[HistoricalGame], team: str) -> list[HistoricalGame]:
    """Get all games where team played away."""
    return [g for g in games if g.away_team == team]


def _compute_net_rating(games: list[HistoricalGame], team: str) -> float:
    """Compute average net rating (points for - points against) per game."""
    if not games:
        return 0.0

    total_diff = 0.0
    for g in games:
        if g.home_team == team:
            total_diff += g.home_score - g.away_score
        else:
            total_diff += g.away_score - g.home_score

    return total_diff / len(games)


def _compute_pace(games: list[HistoricalGame]) -> float:
    """Compute average pace (total points / 2) per game."""
    if not games:
        return 100.0  # Default NBA average pace approximation

    total_points = sum((g.home_score + g.away_score) / 2 for g in games)
    return total_points / len(games)


def _compute_win_pct(games: list[HistoricalGame], team: str) -> float:
    """Compute win percentage for a team in given games."""
    if not games:
        return 0.5  # Default to .500 if no games

    wins = 0
    for g in games:
        if g.home_team == team:
            wins += 1 if g.home_win else 0
        else:
            wins += 1 if not g.home_win else 0

    return wins / len(games)


def _compute_home_win_pct(games: list[HistoricalGame], team: str) -> float:
    """Compute win percentage for team when playing at home."""
    if not games:
        return 0.5  # Default

    wins = sum(1 for g in games if g.home_win)
    return wins / len(games)


def _compute_away_win_pct(games: list[HistoricalGame], team: str) -> float:
    """Compute win percentage for team when playing away."""
    if not games:
        return 0.5  # Default

    wins = sum(1 for g in games if not g.home_win)
    return wins / len(games)
