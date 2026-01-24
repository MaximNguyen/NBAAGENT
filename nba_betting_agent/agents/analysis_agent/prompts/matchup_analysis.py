"""Prompt templates for LLM matchup analysis."""

MATCHUP_ANALYSIS_PROMPT = '''Analyze this NBA matchup for betting insights.

Game: {away_team} @ {home_team}
Date: {game_date}

## Team Statistics

### {home_team} (Home)
{home_stats}

### {away_team} (Away)
{away_stats}

## Injuries
{injuries}

## Current Lines
{odds_summary}

---

Analyze the following factors and their betting implications:

1. **Injury Impact**: How do current injuries affect rotation, matchups, and scoring?
2. **Rest & Travel**: Any back-to-back situations, long road trips, or home stands?
3. **Recent Form**: How are teams trending over last 5-10 games?
4. **Matchup Dynamics**: Historical head-to-head, stylistic matchups (pace, defense type)
5. **Motivation Factors**: Playoff positioning, revenge games, division rivalry
6. **Market Signals**: Any suspicious line movements or public vs sharp money indicators?

Provide your analysis in this structure:

## Key Factors Favoring {home_team}
[Bullet points]

## Key Factors Favoring {away_team}
[Bullet points]

## Biggest Mismatch or Advantage
[One clear insight the market might undervalue]

## Risk Factors
[What could make any prediction wrong - variance, uncertainty]

## Contrarian Angle
[Any overlooked factor that contradicts public sentiment]

Keep analysis factual and tied to the provided data. Do not invent statistics.'''


def format_matchup_prompt(
    home_team: str,
    away_team: str,
    game_date: str,
    home_stats: str,
    away_stats: str,
    injuries: str,
    odds_summary: str
) -> str:
    """Format the matchup analysis prompt with game data.

    Args:
        home_team: Home team name
        away_team: Away team name
        game_date: Game date string
        home_stats: Formatted home team statistics
        away_stats: Formatted away team statistics
        injuries: Formatted injury report
        odds_summary: Current odds from multiple books

    Returns:
        Formatted prompt string ready for LLM
    """
    return MATCHUP_ANALYSIS_PROMPT.format(
        home_team=home_team,
        away_team=away_team,
        game_date=game_date,
        home_stats=home_stats,
        away_stats=away_stats,
        injuries=injuries,
        odds_summary=odds_summary
    )


def format_team_stats(stats: dict) -> str:
    """Format TeamStats dict into readable string for prompt.

    Args:
        stats: TeamStats dictionary (can be Pydantic model dict or plain dict)

    Returns:
        Formatted multi-line string with team statistics
    """
    if not stats:
        return "No stats available"

    lines = []

    # Handle record
    if 'record' in stats:
        record = stats['record']
        if isinstance(record, dict):
            lines.append(f"Record: {record.get('wins', 0)}-{record.get('losses', 0)}")
        else:
            # Pydantic model
            lines.append(f"Record: {record.wins}-{record.losses}")

    # Handle basic stats
    if 'stats' in stats:
        s = stats['stats']
        if isinstance(s, dict):
            pts = s.get('pts', 'N/A')
            reb = s.get('reb', 'N/A')
            ast = s.get('ast', 'N/A')
            fg_pct = s.get('fg_pct', 0)
            fg3_pct = s.get('fg3_pct', 0)
        else:
            # Pydantic model
            pts = s.pts
            reb = s.reb
            ast = s.ast
            fg_pct = s.fg_pct
            fg3_pct = s.fg3_pct

        lines.append(f"PPG: {pts}, RPG: {reb}, APG: {ast}")
        lines.append(f"FG%: {fg_pct*100:.1f}%, 3P%: {fg3_pct*100:.1f}%")

    # Handle advanced metrics
    if 'advanced' in stats and stats['advanced']:
        a = stats['advanced']
        if isinstance(a, dict):
            off_rtg = a.get('off_rtg', 'N/A')
            def_rtg = a.get('def_rtg', 'N/A')
            net_rtg = a.get('net_rtg', 'N/A')
            pace = a.get('pace', 'N/A')
        else:
            # Pydantic model
            off_rtg = a.off_rtg
            def_rtg = a.def_rtg
            net_rtg = a.net_rtg
            pace = a.pace

        lines.append(f"ORtg: {off_rtg}, DRtg: {def_rtg}, NetRtg: {net_rtg}")
        lines.append(f"Pace: {pace}")

    # Handle last 10 games
    if 'last_10' in stats and stats['last_10']:
        l10 = stats['last_10']
        if isinstance(l10, dict):
            record = l10.get('record', 'N/A')
            pts = l10.get('pts', 'N/A')
        else:
            # Pydantic model
            record = l10.record
            pts = l10.pts

        lines.append(f"Last 10: {record}, PPG: {pts}")

    return '\n'.join(lines) if lines else "No stats available"


def format_injuries(injuries: list) -> str:
    """Format injury list into readable string for prompt.

    Args:
        injuries: List of injury dictionaries

    Returns:
        Formatted multi-line string with injury reports
    """
    if not injuries:
        return "No injuries reported"

    lines = []
    for inj in injuries:
        # Handle both dict and Pydantic model
        if isinstance(inj, dict):
            player = inj.get('player', 'Unknown')
            status = inj.get('status', 'Unknown')
            injury_type = inj.get('injury', 'Unknown')
            team = inj.get('team', '')
        else:
            # Pydantic model
            player = inj.player
            status = inj.status
            injury_type = inj.injury
            team = inj.team

        lines.append(f"- {player} ({team}): {status} - {injury_type}")

    return '\n'.join(lines)


def format_odds_summary(odds_data: list) -> str:
    """Format odds data into readable string for prompt.

    Args:
        odds_data: List of GameOdds dictionaries

    Returns:
        Formatted multi-line string with odds from multiple books
    """
    if not odds_data:
        return "No odds available"

    lines = []

    # Process first game only for single matchup analysis
    for game in odds_data[:1]:
        # Handle both dict and Pydantic model
        if isinstance(game, dict):
            bookmakers = game.get('bookmakers', [])
        else:
            bookmakers = game.bookmakers

        # Show top 3 books
        for book in bookmakers[:3]:
            if isinstance(book, dict):
                book_name = book.get('title', book.get('key', 'Unknown'))
                markets = book.get('markets', [])
            else:
                book_name = book.title
                markets = book.markets

            # Find h2h market
            for market in markets:
                if isinstance(market, dict):
                    market_key = market.get('key')
                    outcomes = market.get('outcomes', [])
                else:
                    market_key = market.key
                    outcomes = market.outcomes

                if market_key == 'h2h' and len(outcomes) >= 2:
                    # Format outcomes
                    if isinstance(outcomes[0], dict):
                        team1 = outcomes[0]['name']
                        price1 = outcomes[0]['price']
                        team2 = outcomes[1]['name']
                        price2 = outcomes[1]['price']
                    else:
                        team1 = outcomes[0].name
                        price1 = outcomes[0].price
                        team2 = outcomes[1].name
                        price2 = outcomes[1].price

                    lines.append(f"{book_name}: {team1} {price1:.2f}, {team2} {price2:.2f}")
                    break

    return '\n'.join(lines) if lines else "No odds available"
