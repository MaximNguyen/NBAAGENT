"""Historical data loading for ML model training.

Provides functions to fetch historical NBA game data and betting odds
for training and backtesting ML probability models.

Uses:
- NBA API (LeagueGameFinder) for historical game results
- The Odds API for historical betting odds
- diskcache for 30-day caching of historical data
"""

import os
import time
from datetime import date, datetime

import httpx
from diskcache import Cache
from dotenv import load_dotenv
from nba_api.stats.endpoints import leaguegamefinder

from nba_betting_agent.ml.data.schema import HistoricalGame, HistoricalOdds
from nba_betting_agent.monitoring import get_logger

log = get_logger()

# Cache configuration: 30-day TTL for historical data (doesn't change)
CACHE_DIR = ".cache/ml_historical"
CACHE_TTL = 30 * 24 * 60 * 60  # 30 days in seconds

# NBA API rate limit: max ~2 requests per second
NBA_API_DELAY = 0.6  # seconds between requests


def _get_cache() -> Cache:
    """Get or create the historical data cache.

    Returns:
        diskcache.Cache instance for historical data
    """
    return Cache(CACHE_DIR)


def load_historical_games(seasons: list[str]) -> list[HistoricalGame]:
    """Load historical NBA game data for specified seasons.

    Fetches completed regular season games from NBA API using LeagueGameFinder.
    Results are cached with 30-day TTL since historical data doesn't change.

    Args:
        seasons: List of season strings (e.g., ["2022-23", "2023-24"])

    Returns:
        List of HistoricalGame objects with game outcomes

    Example:
        games = load_historical_games(["2023-24"])
        print(f"Loaded {len(games)} games")
        for game in games[:5]:
            print(f"{game.away_team} @ {game.home_team}: {game.away_score}-{game.home_score}")
    """
    cache = _get_cache()
    all_games: list[HistoricalGame] = []

    for season in seasons:
        cache_key = f"nba_games:{season}"

        # Check cache first
        cached_data = cache.get(cache_key)
        if cached_data is not None:
            log.info("historical_games_cache_hit", season=season, game_count=len(cached_data))
            all_games.extend(cached_data)
            continue

        log.info("historical_games_fetch_started", season=season)
        start_time = time.perf_counter()

        try:
            # Fetch from NBA API - Regular Season games only
            # season_type_all_star: 1=All-Star, 2=Regular Season, 3=Playoffs
            finder = leaguegamefinder.LeagueGameFinder(
                season_nullable=season,
                season_type_nullable="Regular Season",
                league_id_nullable="00",  # NBA
            )

            # Rate limit
            time.sleep(NBA_API_DELAY)

            df = finder.get_data_frames()[0]

            if df.empty:
                log.warning("historical_games_empty", season=season)
                cache.set(cache_key, [], expire=CACHE_TTL)
                continue

            # Group by GAME_ID to get both teams' data for each game
            games_by_id: dict[str, list[dict]] = {}
            for _, row in df.iterrows():
                game_id = row["GAME_ID"]
                if game_id not in games_by_id:
                    games_by_id[game_id] = []
                games_by_id[game_id].append(row.to_dict())

            season_games: list[HistoricalGame] = []

            for game_id, rows in games_by_id.items():
                if len(rows) != 2:
                    # Skip games without both teams' data
                    continue

                # Determine home/away from MATCHUP column
                # "vs." indicates home game, "@" indicates away game
                home_row = None
                away_row = None

                for row in rows:
                    matchup = row.get("MATCHUP", "")
                    if "vs." in matchup:
                        home_row = row
                    elif "@" in matchup:
                        away_row = row

                if not home_row or not away_row:
                    continue

                # Parse game date
                game_date_str = home_row.get("GAME_DATE", "")
                try:
                    game_date = datetime.strptime(game_date_str, "%Y-%m-%d")
                except ValueError:
                    log.warning("invalid_game_date", game_id=game_id, date_str=game_date_str)
                    continue

                # Create HistoricalGame
                game = HistoricalGame(
                    game_id=game_id,
                    game_date=game_date,
                    season=season,
                    home_team=home_row.get("TEAM_ABBREVIATION", "UNK"),
                    away_team=away_row.get("TEAM_ABBREVIATION", "UNK"),
                    home_score=int(home_row.get("PTS", 0)),
                    away_score=int(away_row.get("PTS", 0)),
                )
                season_games.append(game)

            # Cache the results
            cache.set(cache_key, season_games, expire=CACHE_TTL)

            duration_ms = int((time.perf_counter() - start_time) * 1000)
            log.info(
                "historical_games_fetch_completed",
                season=season,
                game_count=len(season_games),
                duration_ms=duration_ms,
            )

            all_games.extend(season_games)

        except Exception as e:
            log.error(
                "historical_games_fetch_failed",
                season=season,
                error=str(e),
                error_type=type(e).__name__,
            )
            # Continue with other seasons

    return all_games


def load_historical_odds(
    start_date: date,
    end_date: date,
    api_key: str | None = None,
) -> list[HistoricalOdds]:
    """Load historical betting odds from The Odds API.

    Fetches historical odds snapshots for NBA games within the date range.
    Results are cached with 30-day TTL.

    Note: The Odds API historical endpoint requires a paid tier for dates
    in the past. Free tier users will get an empty list with a warning.

    Args:
        start_date: Start date for odds retrieval (inclusive)
        end_date: End date for odds retrieval (inclusive)
        api_key: The Odds API key. If None, reads from THE_ODDS_API_KEY env var.

    Returns:
        List of HistoricalOdds objects, empty if API key missing or API error

    Example:
        from datetime import date
        odds = load_historical_odds(
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31),
        )
        print(f"Loaded {len(odds)} odds records")
    """
    load_dotenv()

    # Get API key from parameter or environment
    key = api_key or os.getenv("THE_ODDS_API_KEY") or os.getenv("ODDS_API_KEY")

    if not key:
        log.warning(
            "historical_odds_no_api_key",
            message="THE_ODDS_API_KEY not set. Cannot fetch historical odds.",
        )
        return []

    cache = _get_cache()
    all_odds: list[HistoricalOdds] = []

    # Iterate through each date in range
    current_date = start_date
    while current_date <= end_date:
        cache_key = f"odds:{current_date.isoformat()}"

        # Check cache first
        cached_data = cache.get(cache_key)
        if cached_data is not None:
            log.debug("historical_odds_cache_hit", date=current_date.isoformat())
            all_odds.extend(cached_data)
            current_date = _next_day(current_date)
            continue

        log.info("historical_odds_fetch_started", date=current_date.isoformat())

        try:
            date_odds = _fetch_odds_for_date(current_date, key)
            cache.set(cache_key, date_odds, expire=CACHE_TTL)
            all_odds.extend(date_odds)

            log.info(
                "historical_odds_fetch_completed",
                date=current_date.isoformat(),
                odds_count=len(date_odds),
            )

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                log.error(
                    "historical_odds_auth_error",
                    message="Invalid API key or insufficient permissions",
                )
                return all_odds  # Stop trying, auth won't work
            elif e.response.status_code == 402:
                log.warning(
                    "historical_odds_payment_required",
                    message="Historical odds require paid API tier",
                    date=current_date.isoformat(),
                )
                # Cache empty list to avoid retrying this date
                cache.set(cache_key, [], expire=CACHE_TTL)
            elif e.response.status_code == 422:
                log.warning(
                    "historical_odds_invalid_date",
                    message="Date may be too far in the past or invalid",
                    date=current_date.isoformat(),
                )
                cache.set(cache_key, [], expire=CACHE_TTL)
            else:
                log.error(
                    "historical_odds_http_error",
                    date=current_date.isoformat(),
                    status_code=e.response.status_code,
                    error=str(e),
                )

        except Exception as e:
            log.error(
                "historical_odds_fetch_failed",
                date=current_date.isoformat(),
                error=str(e),
                error_type=type(e).__name__,
            )

        current_date = _next_day(current_date)

    return all_odds


def _next_day(d: date) -> date:
    """Get the next day.

    Args:
        d: Current date

    Returns:
        Next day as date
    """
    from datetime import timedelta

    return d + timedelta(days=1)


def _fetch_odds_for_date(target_date: date, api_key: str) -> list[HistoricalOdds]:
    """Fetch odds for a specific date from The Odds API.

    Args:
        target_date: Date to fetch odds for
        api_key: The Odds API key

    Returns:
        List of HistoricalOdds for that date

    Raises:
        httpx.HTTPStatusError: On API error
    """
    base_url = "https://api.the-odds-api.com/v4/historical/sports/basketball_nba/odds"

    # Format date as ISO string for API
    date_str = target_date.isoformat()

    params = {
        "apiKey": api_key,
        "regions": "us",
        "markets": "h2h,spreads,totals",
        "oddsFormat": "decimal",
        "date": f"{date_str}T12:00:00Z",  # Noon UTC snapshot
    }

    with httpx.Client(timeout=30.0) as client:
        response = client.get(base_url, params=params)
        response.raise_for_status()

    data = response.json()
    odds_list: list[HistoricalOdds] = []

    # Parse timestamp from response or use target date
    timestamp_str = data.get("timestamp")
    if timestamp_str:
        try:
            timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
        except ValueError:
            timestamp = datetime.combine(target_date, datetime.min.time())
    else:
        timestamp = datetime.combine(target_date, datetime.min.time())

    # Parse games data
    games_data = data.get("data", [])
    for game in games_data:
        game_id = game.get("id", "")
        commence_time_str = game.get("commence_time", "")

        try:
            game_date = datetime.fromisoformat(commence_time_str.replace("Z", "+00:00"))
        except ValueError:
            game_date = datetime.combine(target_date, datetime.min.time())

        # Parse each bookmaker's odds
        for bookmaker in game.get("bookmakers", []):
            book_key = bookmaker.get("key", "")

            for market in bookmaker.get("markets", []):
                market_key = market.get("key", "")

                for outcome in market.get("outcomes", []):
                    odds_entry = HistoricalOdds(
                        game_id=game_id,
                        game_date=game_date,
                        bookmaker=book_key,
                        market=market_key,
                        outcome=outcome.get("name", ""),
                        price=float(outcome.get("price", 0.0)),
                        point=outcome.get("point"),
                        timestamp=timestamp,
                    )
                    odds_list.append(odds_entry)

    return odds_list
