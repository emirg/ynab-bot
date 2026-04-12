# ADR: Migrate Financial Advisor Foundations To PostgreSQL In Phase 1

## Metadata
- **Status:** Accepted
- **Date:** 2026-04-12
- **Related Spec:** `docs/specs/2026-03-21-financial-advisor-web-app.md`
- **Related Plan:** `docs/plans/2026-03-21-phase1-foundations.md`
- **Supersedes:** None
- **Superseded By:** None

## Context
The financial advisor will add a more web-oriented, analysis-heavy surface on top of the current bot. The current runtime still uses SQLite-only repositories backed by `DatabaseManager` and a v9 migration history, but the project already anticipates broader HTTP usage, richer read models, and more persistence-sensitive feature work during the advisor rollout.

Leaving the persistence choice open would keep Phase 1 ambiguous and could cause duplicated work:
- stabilizing boundaries around SQLite first
- then redesigning those same boundaries again for PostgreSQL
- or postponing integration-test and migration work until later phases when the advisor already depends on the old storage model

The repository also already includes optional local PostgreSQL development scaffolding, which lowers the cost of deciding now, but that scaffolding is not yet an adopted runtime architecture.

## Decision
Phase 1 of the financial advisor will include a migration from the current SQLite runtime persistence to PostgreSQL.

This means Phase 1 must deliver:
- PostgreSQL-backed implementations for the current persistence interfaces
- a migration path from the current SQLite data model into PostgreSQL
- configuration and integration-test support for PostgreSQL
- container/runtime wiring that preserves the existing Telegram bot, OAuth flow, and authenticated HTTP expense endpoint during the cutover

Until cutover is complete, SQLite remains the current production baseline. Existing SQLite behavior and tests are the compatibility reference, not the target end state.

## Alternatives Considered
- **Option A:** Keep persistence undecided until later advisor phases.
  Rejected because it leaves the foundational phase underspecified and increases the chance of rework when later advisor features need a different persistence model.
- **Option B:** Keep SQLite for all of Phase 1 and revisit PostgreSQL later.
  Rejected because the user explicitly wants the migration in Phase 1, and deferring it would separate infrastructure foundations from the advisor rollout they are meant to support.
- **Option C:** Migrate immediately without documenting the decision.
  Rejected because persistence strategy is a long-lived architectural choice and must be explicit before implementation planning continues.

## Consequences
- **Positive:** Phase 1 now has a concrete persistence target and can sequence migration, testing, and cutover work against it.
- **Positive:** Advisor follow-on phases can assume a PostgreSQL baseline instead of re-opening the storage decision.
- **Negative:** Phase 1 becomes larger and higher risk because it includes both boundary stabilization and a real database migration.
- **Negative:** Current invariants and architecture docs that still describe SQLite as the active runtime baseline will need coordinated updates once implementation lands.
- **Follow-up:** The Phase 1 plan must treat PostgreSQL migration as required scope, not an optional branch.
- **Follow-up:** Implementation must preserve per-user isolation, YNAB milliunit handling, Spanish UI copy, OAuth behavior, and the current authenticated HTTP expense API during and after cutover.

## References
- `docs/plans/2026-03-21-phase1-foundations.md`
- `docs/specs/2026-03-21-financial-advisor-web-app.md`
- `docs/ARCHITECTURE.md`
- `src/infrastructure/repositories/database_manager.py`
- `src/infrastructure/container.py`
- `docker-compose.yml`
