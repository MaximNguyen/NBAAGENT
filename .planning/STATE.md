# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-07)

**Core value:** Find genuine edges in NBA betting markets by comparing AI-generated probability estimates against sportsbook odds — security hardening protects this system and its users.
**Current focus:** Phase 4 - Database & WebSocket Hardening (Phase 3 complete)

## Current Position

Phase: 4 of 5 (Database & WebSocket Hardening)
Plan: 1 of 2 in current phase
Status: In progress
Last activity: 2026-02-08 — Completed 04-01-PLAN.md (Database Engine Hardening)

Progress: [████████████████████░░░░] 50% of Phase 4 (1/2 plans complete)

## Performance Metrics

**Velocity:**
- Total plans completed: 7
- Average duration: 2.7 min
- Total execution time: 0.31 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01 | 2/2 | 7 min | 3.5 min |
| 02 | 2/2 | 5 min | 2.5 min |
| 03 | 2/2 | 7 min | 3.5 min |
| 04 | 1/2 | 1 min | 1.0 min |

**Recent Trend:**
- Last 5 plans: 3min, 4min, 3min, 1min
- Trend: Accelerating - recent plan significantly faster

*Updated after each plan completion*

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- **[01-01]** JWT_SECRET_KEY minimum length 32 characters (catches weak secrets at startup)
- **[01-01]** Settings uses lru_cache singleton pattern (config loaded once per application)
- **[01-01]** All auth secrets required with no defaults (fail-fast if missing)
- **[01-01]** Token expiry defaults: 60min access, 7day refresh (configurable ranges)
- **[01-02]** PyJWT replaces custom HMAC-SHA256 JWT (algorithm verification, automatic expiration)
- **[01-02]** Bcrypt (12 rounds) replaces SHA-256 password hashing (GPU-resistant, salted)
- **[01-02]** Token type claims (access vs refresh) prevent token confusion attacks
- **[01-02]** bcrypt downgraded to <5.0.0 for passlib compatibility
- **[02-01]** Security headers include cdn.jsdelivr.net in CSP for Swagger UI docs page
- **[02-01]** Request logging uses X-Envoy-External-Address header for Railway proxy, falls back to request.client.host for local dev
- **[02-01]** Health check endpoints (/api/health, /healthcheck) excluded from request logging to reduce noise
- **[02-01]** Authorization headers never bound to contextvars, so never appear in logs (sensitive data redaction by design)
- **[02-01]** Middleware registered in reverse execution order: RequestLogging, SecurityHeaders, CORS (executes as CORS first, logging last)
- **[02-01]** CORS tightened from wildcard allow_methods/allow_headers to explicit lists (GET/POST/DELETE, Content-Type/Authorization)
- **[02-02]** EV thresholds constrained to -1.0 to 1.0 range (prevents invalid filter values)
- **[02-02]** Limit parameter capped at 100 results (prevents resource exhaustion)
- **[02-02]** String parameters have max_length constraints: team=10, market=50, sort_by=50, confidence=20, season=10, game_id=100, run_id=100
- **[03-01]** IP-based rate limiting (not user-based) appropriate for single-user system
- **[03-01]** Tiered rate limits: 5/15min login, 10/min write, 100/min read, 30/min refresh (security vs usability balance)
- **[03-01]** SlowAPI chosen over custom middleware (RFC compliance, Retry-After headers, storage backends)
- **[03-02]** jti claims in both access and refresh tokens enable per-token revocation
- **[03-02]** In-memory blacklist suitable for single-instance deployment (expires naturally with tokens)
- **[03-02]** Token blacklist cleanup on each revoke call prevents unbounded growth
- **[03-02]** threading.Lock correct for AnalysisStore (not asyncio.Lock) because WebSocket analysis runs in ThreadPoolExecutor
- **[03-02]** ConnectionManager enforces 2 concurrent WebSocket connections per user, rejecting excess with close code 4003
- **[04-01]** Pool defaults (pool_size=10, max_overflow=20) balanced for Railway single-instance deployment, configurable via DB_POOL_SIZE/DB_MAX_OVERFLOW env vars
- **[04-01]** SSL with CERT_REQUIRED only for production PostgreSQL (development SQLite and non-production PostgreSQL skip SSL)
- **[04-01]** hide_parameters=True always enabled to prevent SQL parameter leakage in logs
- **[04-01]** Engine factory try/except allows CLI/migration operation without JWT_SECRET_KEY/DASHBOARD_PASSWORD_HASH env vars
- **[04-01]** asyncpg added to api optional dependencies (not base) since only dashboard connects to PostgreSQL

### Pending Todos

None yet.

### Blockers/Concerns

**Phase 1 Complete - Critical Security Note:**
- ✅ Hardcoded credentials removed from source code
- ⚠️ Old credentials in git history (`Maxim03` password, `nba-ev-dashboard-secret` key) are permanently compromised
- ⚠️ Users MUST generate fresh secrets - NEVER reuse compromised values from history

**Technical Concerns:**
- bcrypt/passlib compatibility: passlib 1.7.4 logs warning with bcrypt 4.x but works correctly. May need upgrade to newer passlib or direct bcrypt usage in future.

**Future Phase Research:**
- Phase 4: WebSocket Sec-WebSocket-Protocol browser compatibility (Safari/Firefox testing needed)

**Phase 3 Complete:**
- IP-based rate limiting with SlowAPI middleware
- JWT token invalidation with jti claims and in-memory blacklist
- Thread-safe AnalysisStore with atomic update methods
- WebSocket connection limits (2 per user, close code 4003 on excess)
- Current implementation suitable for single Railway instance (in-memory storage)
- If scaling to multiple instances, consider Redis backend for shared state (future optimization)

## Session Continuity

Last session: 2026-02-08
Stopped at: Completed Plan 04-01 (Database Engine Hardening) — Phase 4 in progress (1/2 complete)
Resume file: .planning/phases/04-database-websocket/04-02-PLAN.md (next plan)

---
*State initialized: 2026-02-07*
*Last updated: 2026-02-08*
