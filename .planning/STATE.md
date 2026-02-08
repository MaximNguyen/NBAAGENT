# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-07)

**Core value:** Find genuine edges in NBA betting markets by comparing AI-generated probability estimates against sportsbook odds — security hardening protects this system and its users.
**Current focus:** Phase 2 - Protocol & Transport Security

## Current Position

Phase: 2 of 5 (Protocol & Transport Security)
Plan: 2 of 2 in current phase
Status: Phase complete
Last activity: 2026-02-07 — Completed 02-02-PLAN.md (Input Validation)

Progress: [████████████████████] 100% of Phase 2 (2/2 plans complete)

## Performance Metrics

**Velocity:**
- Total plans completed: 4
- Average duration: 3.0 min
- Total execution time: 0.20 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01 | 2/2 | 7 min | 3.5 min |
| 02 | 2/2 | 5 min | 2.5 min |

**Recent Trend:**
- Last 5 plans: 3min, 4min, 2min, 3min
- Trend: Steady pace, efficient execution

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
- Phase 2: Rate limiting implementation ready (auth foundation complete)
- Phase 3: Railway Redis addon setup (pricing, configuration for distributed rate limiting)
- Phase 4: WebSocket Sec-WebSocket-Protocol browser compatibility (Safari/Firefox testing needed)

## Session Continuity

Last session: 2026-02-07
Stopped at: Completed Plan 02-02 (Input Validation) - Phase 2 complete
Resume file: Phase 3 planning (Database Layer Security)

---
*State initialized: 2026-02-07*
*Last updated: 2026-02-08*
