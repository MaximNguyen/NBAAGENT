# Roadmap: NBA Betting Agent Security Hardening

## Overview

This roadmap transforms a working NBA betting agent from prototype to production-ready by replacing custom security implementations with battle-tested standards. The journey follows a foundation-first approach: establish environment-based configuration and proper authentication (Phase 1), add defense-in-depth middleware layers (Phase 2-3), harden database and persistent connections (Phase 4), then lock down deployment infrastructure (Phase 5). Every phase addresses critical security vulnerabilities identified in codebase review while maintaining the existing LangGraph architecture.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Authentication & Configuration Foundation** - Replace custom JWT/passwords with PyJWT/bcrypt, move secrets to environment ✓ 2026-02-07
- [x] **Phase 2: Protocol & Transport Security** - Add security headers, HTTPS enforcement, CORS tightening, request logging ✓ 2026-02-07
- [x] **Phase 3: Rate Limiting & Concurrency Safety** - Implement rate limiting, fix thread-unsafe global state ✓ 2026-02-08
- [ ] **Phase 4: Database & WebSocket Hardening** - Configure connection pooling, SSL, secure WebSocket auth pattern
- [ ] **Phase 5: Deployment & Supply Chain Security** - Non-root container, health checks, dependency scanning

## Phase Details

### Phase 1: Authentication & Configuration Foundation
**Goal**: All secrets are environment-managed and authentication uses industry-standard libraries
**Depends on**: Nothing (foundation phase)
**Requirements**: AUTH-01, AUTH-02, AUTH-03, AUTH-04, AUTH-05, AUTH-06, AUTH-07
**Success Criteria** (what must be TRUE):
  1. App crashes at startup if JWT_SECRET_KEY or DASHBOARD_PASSWORD_HASH environment variables are missing
  2. User can log in with bcrypt-hashed password and receive PyJWT-encoded access token (1hr expiry) and refresh token (7 day expiry)
  3. User can refresh expired access token using valid refresh token without re-entering password
  4. No credentials (passwords, JWT secrets, API keys) exist in source code or git history
  5. All API endpoints reject requests with invalid inputs (strings too long, numbers out of range)
**Plans**: 2 plans

Plans:
- [x] 01-01-PLAN.md — Configuration foundation: Settings class, dependency installation, FastAPI DI setup ✓
- [x] 01-02-PLAN.md — Auth rewrite: PyJWT tokens, bcrypt passwords, login/refresh endpoints, tests ✓

### Phase 2: Protocol & Transport Security
**Goal**: All API traffic is secured with proper headers, HTTPS, and controlled CORS
**Depends on**: Phase 1 (needs settings.cors_origins, settings.allowed_hosts)
**Requirements**: TRNS-01, TRNS-02, TRNS-03, TRNS-04, TRNS-05, TRNS-06
**Success Criteria** (what must be TRUE):
  1. All API responses include security headers (HSTS, X-Frame-Options: DENY, X-Content-Type-Options: nosniff, CSP)
  2. CORS only allows configured production origins, explicit methods (GET, POST, DELETE), and explicit headers (Content-Type, Authorization)
  3. All API requests are logged with timestamp, method, path, status code, duration, source IP
  4. Authorization headers and API keys are redacted from all logs
  5. All endpoints validate input with Pydantic Field() constraints
**Plans**: 2 plans

Plans:
- [x] 02-01-PLAN.md — Middleware stack: security headers, request logging, CORS tightening ✓
- [x] 02-02-PLAN.md — Input validation: Query()/Path() constraints on all endpoints ✓

### Phase 3: Rate Limiting & Concurrency Safety
**Goal**: API is protected from abuse and concurrent access is thread-safe
**Depends on**: Phase 1, 2 (needs config, middleware stack established)
**Requirements**: RATE-01, RATE-02, RATE-03, RATE-04, RATE-05
**Success Criteria** (what must be TRUE):
  1. Login endpoint rejects 6th attempt from same IP within 15 minutes with 429 status code
  2. API endpoints are rate-limited to prevent abuse and cost spikes
  3. Multiple concurrent requests accessing analysis_store do not cause race conditions or data corruption
  4. User cannot open more than 2 WebSocket connections simultaneously
  5. User can log out and subsequent requests with same token are rejected with 401 status
**Plans**: 2 plans

Plans:
- [x] 03-01-PLAN.md — Rate limiting: SlowAPI setup, login 5/15min, per-endpoint API limits ✓
- [x] 03-02-PLAN.md — Token blacklist/logout, AnalysisStore lock coverage, WebSocket connection limits ✓

### Phase 4: Database & WebSocket Hardening
**Goal**: Data layer and persistent connections are secure and properly configured
**Depends on**: Phase 1 (needs settings.database_url, settings.jwt_secret_key)
**Requirements**: DATA-01, DATA-02, DATA-03, DATA-04, DATA-05
**Success Criteria** (what must be TRUE):
  1. SQLAlchemy connection pool prevents resource exhaustion with configured size limits (pool_size, max_overflow)
  2. PostgreSQL connections use SSL in production environment
  3. SQL parameters do not appear in application logs
  4. WebSocket authentication uses Sec-WebSocket-Protocol header instead of query parameter (token not visible in logs)
  5. HistoricalOddsModel upsert operations work correctly without unique constraint violations
**Plans**: 2 plans

Plans:
- [ ] 04-01-PLAN.md — Database engine hardening: pool limits, production SSL, hidden parameters
- [ ] 04-02-PLAN.md — WebSocket Sec-WebSocket-Protocol auth, HistoricalOddsModel unique constraint

### Phase 5: Deployment & Supply Chain Security
**Goal**: Application runs securely in production with monitored dependencies
**Depends on**: Phase 1-4 (app must be secure before containerization)
**Requirements**: DEPL-01, DEPL-02, DEPL-03, DEPL-04, DEPL-05, DEPL-06
**Success Criteria** (what must be TRUE):
  1. Docker container runs as non-root user (appuser, not root)
  2. Health check endpoint (/health) returns 200 OK when app is ready
  3. Docker HEALTHCHECK instruction monitors app health and reports to Railway
  4. CI/CD pipeline fails build if pip-audit detects known vulnerabilities in dependencies
  5. Dependabot creates automated PRs for security updates
  6. Dependencies are locked in requirements.lock or poetry.lock file
**Plans**: TBD

Plans:
- [ ] 05-01: [TBD during planning]

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Authentication & Config | 2/2 | ✓ Complete | 2026-02-07 |
| 2. Protocol & Transport | 2/2 | ✓ Complete | 2026-02-07 |
| 3. Rate Limiting & Concurrency | 2/2 | ✓ Complete | 2026-02-08 |
| 4. Database & WebSocket | 0/TBD | Not started | - |
| 5. Deployment & Supply Chain | 0/TBD | Not started | - |

---
*Roadmap created: 2026-02-07*
*Last updated: 2026-02-08 after Phase 3 completion*
