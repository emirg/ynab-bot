# Plan: Phase 1 Foundations for the Financial Advisor

## Objective & Context
- **Status:** Draft
- **Source Spec:** `docs/specs/2026-03-21-financial-advisor-web-app.md`
- **Goal:** Prepare the current codebase for the future financial advisor without breaking the Telegram bot, the existing OAuth flow, or the current public HTTP API.
- **Approach:** Phase 1 stays grounded in the current single-repo, single-public-server reality. It first locks the architectural decisions that were previously implicit, then introduces the persistence and boundary changes needed for later advisor work in a reversible, testable sequence.

## Affected Components
- `docs/adrs/` — architecture decisions required before persistence and packaging changes
- `src/infrastructure/repositories/` — current SQLite persistence and future replacement seam
- `src/infrastructure/config/app_config.py` — config needed for any database transition
- `src/infrastructure/container.py` — DI wiring for current and future repository implementations
- `src/presentation/http/` and `src/infrastructure/health.py` — current public HTTP surface that must remain stable
- `tests/` — regression coverage plus any new integration coverage
- `docs/ARCHITECTURE.md`, `docs/AI_WORKFLOW.md`, `README.md` — only if implementation finalizes decisions that change project invariants

## Prerequisites (Manual)
- [ ] Back up the current SQLite database before any migration work starts.
- [ ] Confirm local PostgreSQL is available for development and integration testing if the persistence ADR chooses PostgreSQL.
- [ ] Confirm Railway environment constraints before locking any deployment topology decision.

## Implementation Steps
*(Models MUST mark steps with [x] as they are completed and save the file)*

### Group 1
<!-- Lock the missing architecture decisions before code changes. -->

#### [ ] Step 1: Record the advisor architecture baseline in an ADR
- **Files:** `docs/adrs/2026-04-11-financial-advisor-architecture-baseline.md`, `docs/ARCHITECTURE.md`
- **Action:** Record that Phase 1 planning starts from the current repo and public HTTP server, not from an assumed future monorepo or mandatory multi-service split. Clarify what is decided now versus deferred to later phases.
- **Tests:** N/A — documentation review only

#### [ ] Step 2: Record the persistence strategy ADR
- **Files:** `docs/adrs/2026-04-11-financial-advisor-persistence-strategy.md`, `docs/AI_WORKFLOW.md`, `docs/ARCHITECTURE.md`
- **Action:** Decide whether Phase 1 will migrate from SQLite to PostgreSQL immediately or stage the migration behind compatibility seams first. If the decision supersedes the current `DatabaseManager` invariant, update the project docs in the same change.
- **Tests:** N/A — documentation review only

### Group 2 (depends on: Group 1)
<!-- Establish safer boundaries in the current repo before swapping infrastructure. -->

#### [ ] Step 3: Inventory the current persistence surface and migration scope
- **Files:** `src/infrastructure/repositories/database_manager.py`, `src/infrastructure/repositories/sqlite_user_repository.py`, `src/infrastructure/repositories/sqlite_learning_repository.py`, `src/infrastructure/repositories/sqlite_split_config_repository.py`, `tests/test_database_manager.py`, `tests/test_sqlite_user_repository.py`, `tests/test_sqlite_learning_repository.py`, `tests/test_sqlite_split_config_repository.py`
- **Action:** Map the exact schema, repository behavior, and test expectations that must be preserved. Produce a concrete migration checklist from current SQLite tables and invariants so the new storage layer does not silently change behavior.
- **Tests:** Existing SQLite repository tests remain green and become the behavioral baseline for later groups

#### [ ] Step 4: Stabilize application boundaries for future advisor reuse
- **Files:** `src/domain/`, `src/application/services/`, `src/presentation/http/`, `main.py`, `tests/conftest.py`
- **Action:** Remove or reduce packaging shortcuts that make reuse harder, but do it within the current repo layout. Any import cleanup or packaging work must preserve the current public HTTP API and Telegram runtime instead of assuming a full directory split in this phase.
- **Tests:** `tests/test_main.py`, `tests/test_http_server.py`, `tests/test_health.py`, and representative service tests pass without import regressions

### Group 3 (depends on: Group 2)
<!-- Introduce the new persistence foundation without cutting over runtime yet. -->

#### [ ] Step 5: Add the selected persistence foundation
- **Files:** `requirements.txt`, `src/infrastructure/config/app_config.py`, new persistence support files under `src/infrastructure/repositories/` or another ADR-approved location
- **Action:** Add the chosen database dependencies and base infrastructure needed for the new persistence layer. This includes connection/session management, schema definitions, and migration tooling only after the ADR has locked the target approach.
- **Tests:** Configuration tests cover new required settings; new infrastructure unit tests validate connection lifecycle and error handling

#### [ ] Step 6: Create migration and integration test scaffolding
- **Files:** `tests/`, migration tooling files, optional local compose/dev files if required by the chosen strategy
- **Action:** Add reproducible integration test support for the target database and create the migration path from current persisted data. The scaffolding must be runnable locally and match the project's real deployment assumptions.
- **Tests:** New integration setup proves the target schema can be created and exercised in tests

### Group 4 (depends on: Group 3)
<!-- Swap repository implementations behind the existing application interfaces. -->

#### [ ] Step 7: Implement replacement repositories behind existing interfaces
- **Files:** New repository implementations under `src/infrastructure/repositories/`, related tests under `tests/`
- **Action:** Re-implement user, learning, and split-config persistence behind the existing repository ABCs. Preserve token handling, per-user isolation, split configuration semantics, and all observable service-level behavior.
- **Tests:** Repository-focused tests mirror current SQLite expectations and add target-database integration coverage

#### [ ] Step 8: Wire the new persistence layer into the container without breaking current surfaces
- **Files:** `src/infrastructure/container.py`, `main.py`, `src/presentation/http/`, `src/infrastructure/health.py`
- **Action:** Cut application wiring over to the new repository implementations while preserving Telegram behavior, OAuth callback handling, health checks, and the existing authenticated HTTP expense endpoint.
- **Tests:** `tests/test_container.py`, `tests/test_bot.py`, `tests/test_http_server.py`, `tests/test_expense_api_handler.py`, and relevant end-to-end smoke coverage pass

### Group 5 (depends on: Group 4)
<!-- Remove obsolete SQLite code only after the new path is validated. -->

#### [ ] Step 9: Remove deprecated SQLite-only runtime code
- **Files:** Obsolete SQLite runtime files, configuration docs, migration references, and tests that are no longer valid after cutover
- **Action:** Delete or archive SQLite-only runtime paths only after the new persistence layer is verified. Keep any one-time migration tooling needed for rollback or audit outside the runtime path.
- **Tests:** Full test suite passes and targeted searches confirm stale runtime references are gone

#### [ ] Step 10: Update project documentation and rollout notes
- **Files:** `docs/ARCHITECTURE.md`, `README.md`, `docs/wip_state.md`, and any relevant ADR references
- **Action:** Update architecture and operational docs to match the implemented foundations. Document rollout steps, rollback expectations, and what later advisor phases can now assume.
- **Tests:** N/A — documentation review only

## Constraints & Architecture
- The plan must preserve current user-facing bot behavior and all Spanish UI strings.
- The existing public HTTP server on Railway remains a protected surface throughout Phase 1.
- Per-user isolation and YNAB milliunit rules remain unchanged.
- The plan must not assume a `bot/api/web/shared` monorepo split unless a separate ADR explicitly approves it.
- If Phase 1 changes the database layer away from `DatabaseManager`, the corresponding invariant docs must be updated in the same implementation stream.
- New persistence work must have real regression coverage before SQLite runtime code is removed.

## Verification
- [ ] Existing Telegram bot flows still work after each cutover step.
- [ ] The current authenticated HTTP expense endpoint still works on the public server.
- [ ] The chosen persistence strategy has automated test coverage and a documented migration path.
- [ ] Documentation and ADRs match the implementation that Phase 1 actually ships.
- [ ] Phase 2 work can start from these foundations without needing to rediscover repo layout, runtime entrypoints, or persistence assumptions.
