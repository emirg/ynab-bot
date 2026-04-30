# Spec: Financial Advisor Phase 2 Access and Authentication

## Metadata
- **Status:** Implemented
- **Harness Roadmap Marker:** E.7
- **Owner:** Codex
- **Related Roadmap Item:** Future Financial Advisor milestone
- **Related Spec:** `docs/specs/archive/2026-03-21-financial-advisor-web-app.md`
- **Related ADRs:** `docs/adrs/2026-04-12-financial-advisor-architecture-baseline.md`, `docs/adrs/2026-04-12-financial-advisor-persistence-strategy.md`

## Summary
Phase 2 delivers the first real user-facing access path to the financial advisor. The advisor remains web-first, but access must still start from Telegram so the current bot identity and YNAB connection remain the source of truth.

This phase introduces a Telegram launch command, a one-time advisor launch link, a per-user HTTP session, an authenticated advisor landing page, and a minimal bootstrap endpoint for future dashboard work.

## Problem
- Phase 1 delivered the runtime and persistence foundation, but there is still no advisor entrypoint, no per-user web authentication model, and no authenticated advisor route on the current public HTTP server.
- The current HTTP authentication model is a shared bearer token for the expense API. That is not suitable for a user-specific advisor web experience.
- Dashboard and AI advisor work should not begin before there is a safe way for a user to enter the advisor and establish a server-side authenticated session.

## Goals
- Let an authorized Telegram user open the advisor from a dedicated bot command.
- Reuse the current public HTTP server for the first advisor-access delivery.
- Create a per-user advisor session without exposing another user's data.
- Provide a minimal advisor landing page and bootstrap payload that future dashboard work can build on.
- Preserve the current Telegram bot, OAuth callback, health route, and authenticated expense API behavior.

## Non-Goals
- Delivering advisor charts, financial metrics, or conversational advice.
- Replacing the existing shared bearer token used by the expense API.
- Introducing a separate advisor frontend app, separate public service, or repo split in this phase.
- Persisting advisor analytics or read models beyond launch/session auth state.

## Expected Behavior
- An authorized user can send `/analisis` in Telegram.
- If the user is missing YNAB connection, budget selection, or default account, the command fails gracefully in Spanish and tells the user what is missing.
- If the user is fully configured, the bot returns a launch link to the advisor.
- The launch link is single-use and short-lived.
- When the user opens the launch link, the server validates it, creates an advisor session, sets an HTTP-only cookie, invalidates the launch token, and redirects the browser to the advisor landing page.
- The advisor landing page is accessible only with a valid advisor session.
- The bootstrap endpoint returns only the authenticated user's bootstrap data.
- The user can log out from the advisor session without affecting their Telegram access or YNAB OAuth connection.

## Inputs and Outputs
- **Inputs:** Telegram `/analisis` command, one-time advisor launch token, advisor session cookie, existing user configuration, existing onboarding state.
- **Outputs:** Advisor launch link, advisor session cookie, advisor landing page HTML, bootstrap JSON payload, logout result.
- **Public Interfaces:** Telegram `/analisis`, `GET /advisor/launch`, `GET /advisor`, `GET /api/v1/advisor/bootstrap`, `POST /api/v1/advisor/logout`.

## Business Rules and Constraints
- Access still starts from Telegram; there is no direct unauthenticated advisor login page.
- User isolation is mandatory for launch tokens, sessions, landing page access, and bootstrap payloads.
- All user-facing copy remains in Spanish.
- The current public HTTP server remains the advisor entry surface during this phase.
- The current shared bearer-token expense API remains unchanged.
- Launch tokens must be single use and short lived.
- Session cookies must be HTTP-only.
- Sensitive token material must not be stored in plaintext at rest.

## Edge Cases and Failure Handling
- If the launch token is missing, invalid, reused, or expired, the user sees an advisor-auth failure page in Spanish and no session is created.
- If the session cookie is missing or invalid, advisor routes return an auth failure and clear the cookie.
- If the user loses required configuration after session creation, bootstrap reflects that state without leaking data.
- If the user has little or no recorded transaction history, bootstrap returns `empty` rather than pretending advisor analysis is ready.
- If advisor auth fails, the existing expense API, health route, and OAuth callback must still work unchanged.

## Acceptance Criteria
- [ ] `/analisis` exists and issues advisor launch links only for authorized, fully configured users.
- [ ] `GET /advisor/launch` validates a one-time token, creates a session, and redirects to `GET /advisor`.
- [ ] `GET /advisor` serves a minimal authenticated advisor landing page.
- [ ] `GET /api/v1/advisor/bootstrap` returns only the current user's bootstrap payload.
- [ ] `POST /api/v1/advisor/logout` clears the session cookie and invalidates the session.
- [ ] Launch tokens and advisor sessions are stored safely in PostgreSQL.
- [ ] Existing health, OAuth callback, Telegram, and expense API behavior remain covered and unchanged.

## Completion Notes
- Implemented on the PostgreSQL runtime baseline.
- `/analisis`, advisor launch/session flow, landing page, bootstrap, and logout are all in place.
- Follow-up work should treat this as the stable auth/access baseline for dashboard and read-model work.
