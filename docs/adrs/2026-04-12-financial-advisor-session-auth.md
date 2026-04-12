# ADR: Use Telegram-Issued One-Time Links And HTTP-Only Cookie Sessions For Financial Advisor Phase 2

## Metadata
- **Status:** Accepted
- **Date:** 2026-04-12
- **Related Spec:** `docs/specs/2026-04-12-financial-advisor-phase2-access-auth.md`
- **Related Plan:** `docs/plans/2026-04-12-financial-advisor-phase2-access-auth.md`

## Context
The financial advisor is a web-first analysis surface, but the project already has a trusted identity source and entry channel: Telegram. After Phase 1, the current public HTTP server and PostgreSQL runtime are stable, but there is still no per-user web authentication model for advisor access.

The existing HTTP expense API uses a shared bearer token. That is suitable for a server-to-server API, but it is not suitable for a user-specific browser session.

## Decision
Phase 2 will use this advisor auth model:
- Telegram issues a short-lived one-time advisor launch link.
- The current public HTTP server validates that launch token.
- On success, the server creates a per-user advisor session stored in PostgreSQL.
- The browser receives an HTTP-only session cookie and is redirected to the advisor landing page.

Launch tokens and session tokens are stored hashed at rest.

## Alternatives Considered
- **Reuse the shared HTTP API key for advisor routes.**
  Rejected because it does not identify a single user and would break per-user isolation.
- **Use browser-visible JWT or bearer tokens as the primary advisor auth model.**
  Rejected for this phase because the first advisor slice does not need cross-client token portability and a server-side session is simpler to revoke, invalidate, and reason about.
- **Introduce a separate advisor auth service immediately.**
  Rejected because the current public HTTP server is already the approved Phase 1 baseline and can host this access layer without adding deployment complexity.

## Consequences
- **Positive:** Advisor access stays rooted in Telegram identity, per-user session state is revocable, and the browser never needs direct access to a long-lived user token.
- **Positive:** The project can add dashboard and advisor APIs behind a standard authenticated web session without changing the bot or the expense API auth model.
- **Negative:** The public HTTP server now owns minimal HTML/session behavior in addition to API routing.
- **Negative:** PostgreSQL schema grows to include launch-token and session tables.

## References
- `docs/specs/archive/2026-03-21-financial-advisor-web-app.md`
- `docs/specs/2026-04-12-financial-advisor-phase2-access-auth.md`
- `docs/plans/archive/2026-03-21-phase1-foundations.md`
- `docs/plans/2026-04-12-financial-advisor-phase2-access-auth.md`
- `docs/adrs/2026-04-12-financial-advisor-architecture-baseline.md`
- `docs/adrs/2026-04-12-financial-advisor-persistence-strategy.md`
