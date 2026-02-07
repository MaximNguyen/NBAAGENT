# NBA Betting Agent Orchestra

## What This Is

A multi-agent Python system that finds positive expected value (+EV) NBA bets by fetching odds from multiple sportsbooks via The Odds API, gathering player/team statistics from NBA API and ESPN, generating probability estimates through LightGBM ML models and LLM analysis, and surfacing the best plays with statistical reasoning. Includes a CLI for personal betting research and a FastAPI + React dashboard for visual analysis.

## Core Value

Find genuine edges in NBA betting markets by comparing AI-generated probability estimates against sportsbook odds — if the system can't identify true +EV, nothing else matters.

## Requirements

### Validated

- ✓ CLI accepts natural language input ("find +ev games tonight", "find best bets for celtics vs lakers") — existing
- ✓ Lines agent fetches odds from DraftKings, FanDuel, BetMGM, Bovada via The Odds API — existing
- ✓ Stats agent gathers team stats, home/away records via NBA API — existing
- ✓ Stats agent gathers injury reports via ESPN API — existing
- ✓ Analysis agent uses AI (Anthropic Claude / Ollama) to analyze matchups — existing
- ✓ Analysis agent calculates probability estimates via market odds + adjustments — existing
- ✓ Analysis agent compares probabilities to market odds and calculates EV — existing
- ✓ Analysis agent identifies lower variance +EV plays with Kelly criterion — existing
- ✓ Communication agent presents ranked +EV plays in terminal via Rich — existing
- ✓ Communication agent explains reasoning with statistical backup — existing
- ✓ System only returns bets for current/upcoming games (not historical) — existing
- ✓ LangGraph orchestration with parallel agent execution — existing
- ✓ ML pipeline with LightGBM, walk-forward validation, feature engineering — existing
- ✓ FastAPI dashboard API with React frontend — existing
- ✓ Database layer with SQLAlchemy async + Alembic migrations — existing
- ✓ Docker + Railway deployment configuration — existing
- ✓ Structured logging with structlog — existing
- ✓ 29-file test suite with temporal anti-leakage validation — existing

### Active

- [ ] Security hardening: move hardcoded credentials to environment variables
- [ ] Security hardening: replace custom JWT with battle-tested library (PyJWT)
- [ ] Security hardening: add rate limiting on auth endpoints
- [ ] Security hardening: tighten CORS configuration
- [ ] Fix HistoricalOddsModel missing composite unique constraint for upsert
- [ ] Fix thread safety on global ML state and analysis store
- [ ] Complete dashboard history router (currently stubs)
- [ ] Complete dashboard WebSocket real-time updates
- [ ] Complete dashboard metrics router
- [ ] Integrate unused analysis modules (arbitrage detection, CLV tracking, RLM detection)
- [ ] Works for any bet type (moneyline, player props, etc.) — player props incomplete
- [ ] Add full E2E integration test (query → analysis → formatted output)

### Out of Scope

- Bet tracking and results history — defer to v2
- Bankroll management / bet sizing UI — defer to v2
- Paid APIs — start with free, upgrade if justified
- Sports other than NBA — focus on one sport first
- Automated bet placement — research tool only, user places bets manually
- Mobile app — web dashboard + CLI for now

## Context

**Agent Architecture (LangGraph):**
The system uses a LangGraph StateGraph with parallel execution:
1. **Lines Agent** — Fetches odds via The Odds API with retry logic and credit tracking
2. **Stats Agent** — Gathers team data from NBA API + injuries from ESPN, with circuit breaker pattern
3. **Analysis Agent** — Generates probabilities (market baseline + ML model + LLM analysis), calculates EV with Kelly criterion
4. **Communication Agent** — Formats results with Rich tables and American odds conversion

**ML Pipeline:**
- LightGBM moneyline model with Platt scaling calibration
- Feature engineering: team net rating, pace, win%, rest days, B2B detection, schedule density
- Walk-forward temporal validation (anti-leakage verified in tests)
- Probability blending: 70% ML model + 30% market (configurable)
- SHAP explainability integration

**Dashboard:**
- FastAPI backend with auth, analysis, odds, metrics, opportunities routers
- React + TypeScript frontend with Tailwind CSS
- WebSocket support for real-time updates (partial)

**Data Storage:**
- SQLAlchemy async with PostgreSQL (prod) / SQLite (dev)
- Alembic migrations for schema management
- diskcache for API response caching with stale-while-revalidate

**Known Issues (from codebase review):**
- Hardcoded password (`Maxim03`) and JWT secret in `api/auth.py`
- Custom JWT implementation instead of standard library
- No rate limiting on API endpoints
- CORS allows all headers/methods
- Thread-unsafe global ML state variables
- HistoricalOddsModel lacks unique constraint needed for upsert logic
- Dashboard history/metrics/WebSocket routers are stubs
- Arbitrage detection, CLV tracker, RLM detector built but not integrated

## Constraints

- **Tech stack**: Python + LangGraph + LightGBM + FastAPI + React — established, don't change
- **Data cost**: The Odds API free tier (500 req/month) — sufficient for live analysis
- **LLM**: Anthropic Claude or local Ollama — both supported
- **Scope**: NBA only — proven system, don't expand yet
- **Deployment**: Docker on Railway — already configured

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Multi-agent LangGraph architecture | Parallel execution, clear separation, state management | ✓ Good |
| Python + LightGBM for ML | Strong ecosystem, fast training, good accuracy | ✓ Good |
| The Odds API for odds data | Reliable, covers major books, free tier sufficient | ✓ Good |
| Hybrid probability model (ML + market + LLM) | Multiple signals improve accuracy | ✓ Good |
| FastAPI + React dashboard | Modern stack, async support, good DX | — Pending (partially implemented) |
| Custom JWT in auth.py | Quick implementation | ⚠️ Revisit — security risk, replace with PyJWT |
| Hardcoded credentials | Quick prototype | ⚠️ Revisit — must move to env vars |

---
*Last updated: 2026-02-07 after codebase review and security assessment*
