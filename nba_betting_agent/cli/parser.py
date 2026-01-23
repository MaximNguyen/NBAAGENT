"""Natural language query parser for NBA betting queries.

Parses queries like:
- "find +ev games tonight"
- "find best bets for celtics vs lakers"
- "show me props for the next week"
"""

import re
from dataclasses import dataclass
from datetime import datetime, timedelta


# Team name to abbreviation mapping
TEAM_ALIASES = {
    # Atlantic Division
    "celtics": "BOS",
    "boston": "BOS",
    "nets": "BKN",
    "brooklyn": "BKN",
    "knicks": "NYK",
    "newyork": "NYK",
    "76ers": "PHI",
    "sixers": "PHI",
    "philadelphia": "PHI",
    "raptors": "TOR",
    "toronto": "TOR",
    # Central Division
    "bulls": "CHI",
    "chicago": "CHI",
    "cavaliers": "CLE",
    "cavs": "CLE",
    "cleveland": "CLE",
    "pistons": "DET",
    "detroit": "DET",
    "pacers": "IND",
    "indiana": "IND",
    "bucks": "MIL",
    "milwaukee": "MIL",
    # Southeast Division
    "hawks": "ATL",
    "atlanta": "ATL",
    "hornets": "CHA",
    "charlotte": "CHA",
    "heat": "MIA",
    "miami": "MIA",
    "magic": "ORL",
    "orlando": "ORL",
    "wizards": "WAS",
    "washington": "WAS",
    # Northwest Division
    "nuggets": "DEN",
    "denver": "DEN",
    "timberwolves": "MIN",
    "wolves": "MIN",
    "minnesota": "MIN",
    "thunder": "OKC",
    "oklahoma": "OKC",
    "blazers": "POR",
    "portland": "POR",
    "jazz": "UTA",
    "utah": "UTA",
    # Pacific Division
    "warriors": "GSW",
    "goldstate": "GSW",
    "clippers": "LAC",
    "lakers": "LAL",
    "losangeles": "LAL",
    "suns": "PHX",
    "phoenix": "PHX",
    "kings": "SAC",
    "sacramento": "SAC",
    # Southwest Division
    "mavericks": "DAL",
    "mavs": "DAL",
    "dallas": "DAL",
    "rockets": "HOU",
    "houston": "HOU",
    "grizzlies": "MEM",
    "memphis": "MEM",
    "pelicans": "NOP",
    "neworleans": "NOP",
    "spurs": "SAS",
    "sanantonio": "SAS",
}


@dataclass
class ParsedQuery:
    """Structured representation of parsed natural language query.

    Attributes:
        original: Original query string
        game_date: Parsed date in ISO format (YYYY-MM-DD) or None
        teams: List of team abbreviations (e.g., ["BOS", "LAL"])
        bet_type: Type of bet (moneyline, spread, props, etc.)
    """

    original: str
    game_date: str | None = None
    teams: list[str] | None = None
    bet_type: str | None = None


def parse_query(query: str) -> ParsedQuery:
    """Parse natural language betting query into structured data.

    Args:
        query: Natural language query string

    Returns:
        ParsedQuery with extracted date, teams, and bet type

    Examples:
        >>> parse_query("find +ev games tonight")
        ParsedQuery(original="find +ev games tonight", game_date="2026-01-23", teams=None, bet_type=None)

        >>> parse_query("find best bets for celtics vs lakers")
        ParsedQuery(original="...", game_date=None, teams=["BOS", "LAL"], bet_type=None)
    """
    query_lower = query.lower()

    # Parse date
    game_date = _parse_date(query_lower)

    # Parse teams
    teams = _parse_teams(query_lower)

    # Parse bet type
    bet_type = _parse_bet_type(query_lower)

    return ParsedQuery(
        original=query,
        game_date=game_date,
        teams=teams,
        bet_type=bet_type,
    )


def _parse_date(query: str) -> str | None:
    """Extract date from query.

    Handles:
    - "tonight" -> today's date
    - "tomorrow" -> tomorrow's date
    - "this week" -> today's date (will filter for next 7 days)
    - Date patterns like "2026-01-24", "01/24", "jan 24"

    Returns:
        ISO date string (YYYY-MM-DD) or None
    """
    today = datetime.now().date()

    # Handle common date keywords
    if "tonight" in query or "today" in query:
        return today.isoformat()

    if "tomorrow" in query:
        return (today + timedelta(days=1)).isoformat()

    if "this week" in query or "next week" in query:
        # Return today - graph will handle filtering for next 7 days
        return today.isoformat()

    # Try ISO date pattern (YYYY-MM-DD)
    iso_match = re.search(r'\b(\d{4}-\d{2}-\d{2})\b', query)
    if iso_match:
        return iso_match.group(1)

    # Try MM/DD pattern
    slash_match = re.search(r'\b(\d{1,2})/(\d{1,2})\b', query)
    if slash_match:
        month, day = slash_match.groups()
        year = today.year
        # If month/day has passed this year, assume next year
        parsed_date = datetime(year, int(month), int(day)).date()
        if parsed_date < today:
            parsed_date = datetime(year + 1, int(month), int(day)).date()
        return parsed_date.isoformat()

    # Try month name patterns (e.g., "jan 24", "january 24")
    month_names = [
        "january", "february", "march", "april", "may", "june",
        "july", "august", "september", "october", "november", "december",
        "jan", "feb", "mar", "apr", "may", "jun",
        "jul", "aug", "sep", "oct", "nov", "dec",
    ]
    for i, month_name in enumerate(month_names):
        month_pattern = rf'\b{month_name}\s+(\d{1,2})\b'
        month_match = re.search(month_pattern, query, re.IGNORECASE)
        if month_match:
            day = int(month_match.group(1))
            month = (i % 12) + 1  # Handle both full and abbreviated names
            year = today.year
            parsed_date = datetime(year, month, day).date()
            if parsed_date < today:
                parsed_date = datetime(year + 1, month, day).date()
            return parsed_date.isoformat()

    return None


def _parse_teams(query: str) -> list[str] | None:
    """Extract team abbreviations from query.

    Handles:
    - Team names: "celtics", "lakers", "76ers"
    - Common aliases: "cavs", "sixers", "warriors"
    - Multiple teams: "celtics vs lakers"

    Returns:
        List of team abbreviations or None
    """
    # Normalize query for matching
    normalized = re.sub(r'[^\w\s]', ' ', query.lower())
    normalized = re.sub(r'\s+', ' ', normalized)

    found_teams = []

    # Check each team alias
    for alias, abbrev in TEAM_ALIASES.items():
        # Word boundary search to avoid partial matches
        pattern = rf'\b{re.escape(alias)}\b'
        if re.search(pattern, normalized):
            if abbrev not in found_teams:
                found_teams.append(abbrev)

    return found_teams if found_teams else None


def _parse_bet_type(query: str) -> str | None:
    """Extract bet type from query.

    Handles:
    - "moneyline" or "ml"
    - "spread" or "line"
    - "over/under" or "total" or "o/u"
    - "props" or "player props"

    Returns:
        Bet type string or None
    """
    query_lower = query.lower()

    if "moneyline" in query_lower or re.search(r'\bml\b', query_lower):
        return "moneyline"

    if "spread" in query_lower or re.search(r'\bline\b', query_lower):
        return "spread"

    if any(term in query_lower for term in ["over/under", "total", "o/u"]):
        return "total"

    if "prop" in query_lower:
        return "props"

    return None
