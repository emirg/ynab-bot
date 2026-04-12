# ADR: Use The Current Single-Repo HTTP Runtime As The Financial Advisor Phase 1 Baseline

## Metadata
- **Status:** Accepted
- **Date:** 2026-04-12
- **Related Spec:** `docs/specs/2026-03-21-financial-advisor-web-app.md`
- **Related Plan:** `docs/plans/2026-03-21-phase1-foundations.md`
- **Supersedes:** None
- **Superseded By:** None

## Context
The financial advisor is planned as a new web-first analysis surface, but the project already ships a working runtime with concrete boundaries:
- one repository
- one public HTTP server on Railway
- Telegram polling only in `APP_MODE=full`
- an existing OAuth callback on the same public server
- an authenticated HTTP expense endpoint delegated through the same server
- HTTP-first local development via `APP_MODE=http-dev`

Older advisor planning mixed product behavior with assumptions about a future monorepo split or mandatory multi-service architecture. Starting implementation from those assumptions would create unnecessary churn before the advisor has even landed on the current runtime.

Phase 1 also needs to preserve the existing service boundaries that are already shared by multiple surfaces, especially the prepare/commit expense flow reused by Telegram and HTTP handlers.

## Decision
Phase 1 will treat the current single-repo, single-public-server runtime as the architecture baseline.

This baseline means:
- The advisor work starts inside the current repository.
- The current public HTTP server remains the authoritative entrypoint for health checks, OAuth callback handling, and authenticated HTTP routes during Phase 1.
- Local development remains HTTP-first through `APP_MODE=http-dev`.
- Telegram and HTTP continue sharing the current application-service boundaries, including the `PreparedExpense` prepare/commit workflow.
- Any later split into dedicated API/web services or a different repo/package topology is explicitly deferred to a later ADR or phase.

## Alternatives Considered
- **Option A:** Assume a future `bot/api/web/shared` split now and start Phase 1 from that target structure.
  Rejected because the split is not yet approved architecture and would force speculative refactors before the advisor foundations are delivered.
- **Option B:** Treat the advisor as requiring a separate public service from the start.
  Rejected because the current public HTTP server already handles health, OAuth, and authenticated API traffic, so Phase 1 can extend the existing runtime safely without introducing a second externally exposed service immediately.
- **Option C:** Leave the runtime baseline implicit and decide case by case during implementation.
  Rejected because Phase 1 needs a stable reference point for persistence changes, boundary cleanup, and rollout safety.

## Consequences
- **Positive:** Phase 1 work is anchored to the runtime the project actually ships today.
- **Positive:** Persistence migration and boundary cleanup can proceed without simultaneously forcing a repo-topology redesign.
- **Positive:** Existing protected surfaces remain explicit: Railway public HTTP, OAuth callback, authenticated expense API, and Telegram bot behavior.
- **Negative:** Some architectural ambitions, such as dedicated advisor services or repo splits, are intentionally deferred instead of resolved now.
- **Follow-up:** Future phases may introduce separate API/web deployment units, but only through a new ADR that references this baseline and explains the migration path.
- **Follow-up:** Implementation must preserve the current public HTTP contract, Telegram behavior, per-user isolation, and YNAB invariants while Phase 1 foundations are delivered.

## References
- `docs/specs/2026-03-21-financial-advisor-web-app.md`
- `docs/plans/2026-03-21-phase1-foundations.md`
- `docs/adrs/2026-04-11-prepared-expense-domain-contract.md`
- `docs/adrs/2026-04-12-financial-advisor-persistence-strategy.md`
- `docs/ARCHITECTURE.md`
- `src/presentation/http/server.py`
- `src/infrastructure/health.py`
- `src/application/services/expense_service.py`
