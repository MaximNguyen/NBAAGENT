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
        min_ev: Minimum EV percentage threshold (e.g., 5.0 for 5%)
        confidence: Confidence level filter ("high", "medium", "low")
        limit: Maximum number of results to show
    """

    original: str
    game_date: str | None = None
    teams: list[str] | None = None
    bet_type: str | None = None
    min_ev: float | None = None
    confidence: str | None = None
    limit: int | None = None


def parse_query(query: str) -> ParsedQuery:
    """Parse natural language betting query into structured data.

    Args:
        query: Natural language query string

    Returns:
        ParsedQuery with extracted date, teams, bet type, and filter parameters

    Examples:
        >>> parse_query("find +ev games tonight")
        ParsedQuery(original="find +ev games tonight", game_date="2026-01-23", teams=None, bet_type=None)

        >>> parse_query("find best bets for celtics vs lakers")
        ParsedQuery(original="...", game_date=None, teams=["BOS", "LAL"], bet_type=None)

        >>> parse_query("high confidence bets over 5% edge")
        ParsedQuery(original="...", confidence="high", min_ev=5.0, ...)
    """
    query_lower = query.lower()

    # Parse date
    game_date = _parse_date(query_lower)

    # Parse teams
    teams = _parse_teams(query_lower)

    # Parse bet type
    bet_type = _parse_bet_type(query_lower)

    # Parse filter parameters
    min_ev = _parse_min_ev(query_lower)
    confidence = _parse_confidence(query_lower)
    limit = _parse_limit(query_lower)

    return ParsedQuery(
        original=query,
        game_date=game_date,
        teams=teams,
        bet_type=bet_type,
        min_ev=min_ev,
        confidence=confidence,
        limit=limit,
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


def _parse_min_ev(query: str) -> float | None:
    """Extract minimum EV threshold from query.

    Handles patterns like:
    - "over 5% edge" -> 5.0
    - "above 10% ev" -> 10.0
    - "more than 2.5% edge" -> 2.5
    - "> 5% ev" -> 5.0
    - "5% edge minimum" -> 5.0
    - "5 edge" (assumes % if context is EV) -> 5.0

    Returns:
        Float EV percentage or None
    """
    # Pattern 1: over/above/more than/> X% edge/ev
    patterns = [
        r'(?:over|above|more than|>\s*)(\d+(?:\.\d+)?)\s*%?\s*(?:ev|edge)',
        r'(\d+(?:\.\d+)?)\s*%\s*(?:ev|edge)\s*(?:or higher|minimum|min)',
        r'(?:ev|edge)\s*(?:of|at|above|over|>\s*)(\d+(?:\.\d+)?)\s*%?',
    ]

    for pattern in patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            return float(match.group(1))

    return None


def _parse_confidence(query: str) -> str | None:
    """Extract confidence level filter from query.

    Handles patterns like:
    - "high confidence bets" -> "high"
    - "medium confidence" -> "medium"
    - "low confidence only" -> "low"
    - "confidence: high" -> "high"
    - "confident bets" -> "high"

    Returns:
        Lowercase confidence level string ("high", "medium", "low") or None
    """
    # Direct pattern: (high|medium|low) confidence
    match = re.search(r'\b(high|medium|low)\s*confidence\b', query, re.IGNORECASE)
    if match:
        return match.group(1).lower()

    # Colon pattern: confidence: (high|medium|low)
    match = re.search(r'confidence\s*:\s*(high|medium|low)\b', query, re.IGNORECASE)
    if match:
        return match.group(1).lower()

    # "confident bets" implies high confidence
    if re.search(r'\bconfident\s+bets?\b', query, re.IGNORECASE):
        return "high"

    return None


def _parse_limit(query: str) -> int | None:
    """Extract result limit from query.

    Handles patterns like:
    - "top 10 bets" -> 10
    - "5 best opportunities" -> 5
    - "show 20" -> 20
    - "first 3" -> 3

    Returns:
        Integer limit or None
    """
    # Pattern: X best/top opportunities/bets
    patterns = [
        r'\b(?:top|best)\s+(\d+)\s+(?:bets?|opportunities|picks?)\b',
        r'\b(\d+)\s+(?:best|top)\s+(?:bets?|opportunities|picks?)\b',
        r'^\s*show\s+(\d+)\b',
        r'\bfirst\s+(\d+)\b',
    ]

    for pattern in patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            return int(match.group(1))

    return None
