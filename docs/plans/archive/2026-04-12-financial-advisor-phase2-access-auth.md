# Plan: Financial Advisor Phase 2 Access and Authentication

## Objective & Context
- **Status:** Completed
- **Source Spec:** `docs/specs/2026-04-12-financial-advisor-phase2-access-auth.md`
- **Goal:** Deliver the first authenticated advisor-access slice on top of the completed PostgreSQL runtime baseline.
- **Approach:** Reuse the current Telegram bot and public HTTP server. Telegram issues a one-time advisor launch link; the public HTTP server exchanges that token for a server-side advisor session stored in PostgreSQL and represented in the browser by an HTTP-only cookie.

## Affected Components
- `src/presentation/telegram/` — new `/analisis` entry command
- `src/application/services/` — advisor access/session/bootstrap orchestration
- `src/domain/repositories/` — new advisor auth persistence interface
- `src/infrastructure/repositories/` — PostgreSQL launch token and session storage
- `src/presentation/http/` and `src/infrastructure/health.py` — advisor routes, cookie auth, landing page, bootstrap/logout endpoints
- `src/infrastructure/container.py` and `src/infrastructure/config/app_config.py` — DI wiring and advisor URL config
- `tests/` — route, service, repository, config, and Telegram command coverage
- `docs/adrs/` — auth/session architecture decision

## Implementation Steps
### Group 1
#### [x] Step 1: Record the advisor auth/session decision in an ADR
- **Files:** `docs/adrs/2026-04-12-financial-advisor-session-auth.md`
- **Action:** Record the current-server, one-time-launch-link, HTTP-only-cookie session model as the Phase 2 advisor auth baseline.
- **Tests:** N/A

#### [x] Step 2: Add the Phase 2 domain and persistence contract
- **Files:** new advisor auth model/repository files under `src/domain/`
- **Action:** Define the launch token/session persistence interface and any domain exceptions needed for advisor access.
- **Tests:** Add focused unit tests if domain-only behavior is introduced.

### Group 2 (depends on: Group 1)
#### [x] Step 3: Extend PostgreSQL schema and repository support
- **Files:** `src/infrastructure/repositories/postgres_schema.py`, new PostgreSQL advisor auth repository, related container wiring
- **Action:** Add migration-backed tables for advisor launch tokens and advisor sessions, storing only hashed token values and expiry metadata.
- **Tests:** Repository and schema tests cover creation, single-use exchange, session lookup, logout, expiry handling, and per-user isolation.

#### [x] Step 4: Implement advisor access orchestration
- **Files:** new advisor access service under `src/application/services/`, `src/infrastructure/config/app_config.py`, `src/infrastructure/container.py`
- **Action:** Implement launch URL generation, launch-token exchange, session creation, session lookup, logout, and bootstrap payload assembly.
- **Tests:** Service tests cover readiness mapping, launch URL generation, token/session lifecycle, and bootstrap state derivation.

### Group 3 (depends on: Group 2)
#### [x] Step 5: Add Telegram advisor entrypoint
- **Files:** new Telegram advisor handler, `src/presentation/telegram/bot.py`
- **Action:** Register `/analisis`, enforce existing authorization, validate onboarding readiness, and return the advisor launch link or the correct Spanish prerequisite message.
- **Tests:** Telegram handler tests cover ready and blocked-by-prerequisite flows plus bot registration coverage.

#### [x] Step 6: Add advisor HTTP routes
- **Files:** `src/presentation/http/server.py`, `src/infrastructure/health.py`, new advisor HTTP handlers and cookie helpers
- **Action:** Add:
  - `GET /advisor/launch`
  - `GET /advisor`
  - `GET /api/v1/advisor/bootstrap`
  - `POST /api/v1/advisor/logout`
  while preserving the current health, OAuth callback, and expense API behavior.
- **Tests:** Health/router/handler tests cover redirect flow, session cookie gating, bootstrap payloads, logout, and invalid-token/session cases.

### Group 4 (depends on: Group 3)
#### [x] Step 7: Update architecture docs and handoff state
- **Files:** `docs/ARCHITECTURE.md`, `docs/wip_state.md`, optionally README if the new advisor entrypoint or env var needs operator visibility
- **Action:** Document the new advisor access baseline and current next milestone boundary.
- **Tests:** N/A

## Constraints & Verification
- Keep all advisor user-facing strings in Spanish.
- Do not change the existing shared bearer-token auth flow for `POST /api/v1/expenses/text`.
- Do not introduce a separate web service or JS build pipeline in this phase.
- Use PostgreSQL as the only runtime persistence target for advisor auth state.
- Verify with targeted pytest runs for new advisor services/repositories/routes plus regression coverage for existing health and bot wiring.

## Completion Notes
- Advisor access/auth now ships on the current public HTTP server with Telegram-issued one-time launch links and HTTP-only advisor sessions.
- This plan is complete and should be archived before starting the next advisor milestone.
