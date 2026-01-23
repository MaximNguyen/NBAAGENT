# NBA Betting Agent Orchestra

## What This Is

A multi-agent Python system that finds positive expected value (+EV) NBA bets by scraping odds from multiple sportsbooks, gathering player/team statistics and news, generating probability estimates through external projections and AI pattern analysis, and surfacing the best plays with statistical reasoning. CLI interface for personal betting research.

## Core Value

Find genuine edges in NBA betting markets by comparing AI-generated probability estimates against sportsbook odds — if the system can't identify true +EV, nothing else matters.

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] CLI accepts natural language input ("find +ev games tonight", "find best bets for celtics vs lakers")
- [ ] Lines agent scrapes odds from Bovada, DraftKings, FanDuel, BetMGM, Hard Rock Bet
- [ ] Stats agent gathers player stats, team stats, home/away records
- [ ] Stats agent gathers injury reports and relevant news
- [ ] Analysis agent pulls external projection sources for probability baselines
- [ ] Analysis agent uses AI to analyze historical/statistical patterns
- [ ] Analysis agent calculates probability estimates for outcomes
- [ ] Analysis agent compares probabilities to market odds and calculates EV
- [ ] Analysis agent identifies lower variance +EV plays
- [ ] Communication agent presents ranked +EV plays in terminal
- [ ] Communication agent explains reasoning with statistical backup (historical data, news, stats)
- [ ] System only returns bets for current/upcoming games (not historical)
- [ ] Works for any bet type (moneyline, player props, etc.) — finds highest EV regardless of type

### Out of Scope

- Bet tracking and results history — MVP focus, add in v2
- Bankroll management / bet sizing — MVP focus, add in v2
- Backtesting against historical data — MVP focus, add in v2
- Paid APIs — start with free/scraping, upgrade if major benefit found
- Sports other than NBA — focus on one sport first
- Web UI or mobile app — terminal CLI only for MVP
- Automated bet placement — research tool only, user places bets manually

## Context

**Agent Architecture:**
The system is an "orchestra" of specialized agents working together:
1. **Lines Agent** — Scrapes odds from 5 sportsbooks, finds discrepancies
2. **Stats Agent** — Gathers player/team data, injuries, news
3. **Analysis Agent** — Generates probability estimates, calculates EV
4. **Communication Agent** — Presents findings with reasoning

**+EV Calculation Logic:**
- Generate probability estimate (e.g., Lakers win 53% of the time)
- Compare to implied probability from odds (e.g., +200 implies ~33%)
- Calculate EV: if true probability > implied probability, bet is +EV
- Prioritize lower variance plays (higher confidence estimates)

**Data Sources (sportsbooks for odds):**
- Bovada
- DraftKings
- FanDuel
- BetMGM
- Hard Rock Bet

**Probability Model (hybrid approach):**
- External projection sources (ESPN, other public models)
- AI analysis of historical patterns and statistics

## Constraints

- **Tech stack**: Python — good ecosystem for data analysis, scraping, AI
- **Data cost**: Free APIs and scraping only for MVP — upgrade later if justified
- **Scope**: NBA only — prove the system works before expanding
- **Interface**: Terminal CLI — keep it simple for MVP

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Multi-agent architecture | Separation of concerns — each agent has clear responsibility | — Pending |
| Python | Strong ecosystem for data/AI work, user preference | — Pending |
| Free/scraping first | Validate approach before investing in paid data | — Pending |
| 5 sportsbooks to start | Good coverage of major platforms, can expand later | — Pending |
| Hybrid probability model | External projections provide baseline, AI adds edge | — Pending |

---
*Last updated: 2025-01-23 after initialization*
