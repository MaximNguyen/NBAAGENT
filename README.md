# NBA Betting Agent

A multi-agent system for finding positive expected value (+EV) NBA betting opportunities using AI-powered analysis and real-time odds data.

## What This Does

NBA Betting Agent compares odds from multiple sportsbooks, calculates expected value using calibrated probability estimates, and identifies bets with a mathematical edge. It uses a LangGraph workflow orchestrating specialized agents for odds collection, statistical analysis, and AI-powered matchup insights.

**Key Value:** Find genuine edges in NBA betting markets by comparing AI-generated probability estimates against sportsbook odds.

## Quick Start

```bash
# Clone and install
git clone https://github.com/yourusername/nba-betting-agent.git
cd nba-betting-agent
pip install -e ".[dev]"

# Configure environment
cp .env.example .env
# Edit .env with your API keys (see docs/SETUP.md for details)

# Run analysis
nba-ev analyze "find +ev games tonight"
```

## Features

- **Real-time Odds**: Pulls odds from 5+ sportsbooks via The Odds API (DraftKings, FanDuel, BetMGM, Bovada, etc.)
- **Calibrated Probabilities**: Uses Platt scaling for probability estimation
- **Expected Value Calculation**: Configurable EV thresholds with Kelly criterion bet sizing
- **AI Matchup Analysis**: Claude-powered insights on team matchups and trends
- **Sharp vs Soft Comparison**: Identifies market inefficiencies between sharp and retail books
- **Reverse Line Movement**: Detects when lines move against public betting patterns
- **Parallel Processing**: Lines and Stats agents execute concurrently for fast analysis
- **LangSmith Tracing**: Optional observability for debugging and performance monitoring
- **Structured Logging**: JSON output for production log aggregation

## Architecture

```
User Query
    |
    v
+-------------------+
|   CLI Parser      |  Natural language query parsing
+-------------------+
    |
    v
+-------------------+
| LangGraph Router  |  Workflow orchestration
+-------------------+
    |
    +----------------+----------------+
    |                                 |
    v                                 v
+-------------+               +-------------+
| Lines Agent |   (parallel)  | Stats Agent |
+-------------+               +-------------+
| - Odds API  |               | - NBA API   |
| - 5+ books  |               | - ESPN      |
| - Caching   |               | - Injuries  |
+-------------+               +-------------+
    |                                 |
    +----------------+----------------+
                     |
                     v
            +----------------+
            | Analysis Agent |
            +----------------+
            | - EV calc      |
            | - Probability  |
            | - Claude LLM   |
            +----------------+
                     |
                     v
            +---------------------+
            | Communication Agent |
            +---------------------+
            | - Formatting        |
            | - Filtering         |
            | - Rich output       |
            +---------------------+
                     |
                     v
              Terminal Output
```

## Usage Examples

```bash
# Find positive EV games for tonight
nba-ev analyze "find +ev games tonight"

# Analyze specific matchup
nba-ev analyze "best bets celtics vs lakers"

# Filter by minimum EV threshold
nba-ev analyze "spreads with edge > 3%" --min-ev 0.05

# Verbose output with details
nba-ev analyze "show all opportunities" --verbose

# Show version
nba-ev version
```

## Data Sources

| Source | Data Provided | Rate Limits |
|--------|---------------|-------------|
| [The Odds API](https://the-odds-api.com) | Real-time odds from DraftKings, FanDuel, BetMGM, Bovada, and more | 500 req/month (free tier) |
| [NBA API](https://github.com/swar/nba_api) | Team statistics, player stats, game logs | No official limits |
| [ESPN](https://www.espn.com) | Injury reports and player status | Unofficial API |
| [Anthropic Claude](https://anthropic.com) | AI-powered matchup analysis | Pay-per-use |

**Data Limitations:**
- Odds API free tier limited to 500 requests/month
- Sharp book access (Pinnacle) may require paid tier
- Public betting percentages require separate data source (not included)
- Historical odds for backtesting not included in free tier

## Configuration

The system requires API keys for odds data and AI analysis. See [docs/SETUP.md](docs/SETUP.md) for complete configuration instructions.

**Required Environment Variables:**
```bash
ODDS_API_KEY=your_odds_api_key      # Required - The Odds API
ANTHROPIC_API_KEY=your_anthropic_key # Required - Claude LLM
```

**Optional (LangSmith Tracing):**
```bash
LANGSMITH_TRACING=true              # Enable tracing
LANGSMITH_API_KEY=your_key          # LangSmith API key
LANGSMITH_PROJECT=nba-betting-agent # Project name
```

## Development

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/ -v

# Run tests with coverage
pytest tests/ --cov=nba_betting_agent

# Run specific test file
pytest tests/test_graph.py -v
```

**Project Structure:**
```
nba_betting_agent/
  agents/
    lines_agent/      # Odds collection and comparison
    stats_agent/      # Statistical data gathering
    analysis_agent/   # EV calculation and AI analysis
  cli/                # Command-line interface
  graph/              # LangGraph workflow definition
  monitoring/         # Logging and observability
tests/                # Test suite
```

## Documentation

- [Detailed Setup Guide](docs/SETUP.md) - Prerequisites, installation, and API key configuration
- [Troubleshooting](docs/TROUBLESHOOTING.md) - Common errors and solutions

## Requirements

- Python 3.11+
- The Odds API key (free tier available)
- Anthropic API key (for Claude LLM)
- Optional: LangSmith account for tracing

## License

MIT License - See LICENSE file for details.

## Disclaimer

**This software is for educational and research purposes only.**

- Sports betting involves significant financial risk
- Past performance does not guarantee future results
- No guarantee of profitability is made or implied
- The authors are not responsible for any financial losses
- Always bet responsibly and within your means
- Check local laws regarding sports betting in your jurisdiction
- This tool provides analysis, not financial advice

**Use at your own risk.** The expected value calculations are estimates based on statistical models and may not reflect actual outcomes.
