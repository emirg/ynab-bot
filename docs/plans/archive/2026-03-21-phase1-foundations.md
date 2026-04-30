# Plan: Phase 1 Foundations for the Financial Advisor

## Objective & Context
- **Status:** Completed
- **Harness Roadmap Marker:** E.6
- **Source Spec:** `docs/specs/archive/2026-03-21-financial-advisor-web-app.md`
- **Goal:** Prepare the current codebase for the future financial advisor without breaking the Telegram bot, the existing OAuth flow, or the current public HTTP API.
- **Approach:** Phase 1 stays grounded in the current single-repo, single-public-server reality. It starts from the codebase as it exists now: SQLite remains the active persistence layer, `DatabaseManager` already uses per-thread runtime connections, and the public HTTP expense endpoint already has shared Pydantic request validation plus constant-time bearer auth. The phase now has an accepted persistence target: migrate runtime persistence to PostgreSQL during Phase 1 while preserving current user-facing and HTTP behavior throughout the transition.

## Affected Components
- `docs/adrs/` — architecture decisions required before persistence and packaging changes
- `src/infrastructure/repositories/` — current SQLite persistence and future replacement seam
- `src/infrastructure/config/app_config.py` — config needed for any database transition
- `src/infrastructure/container.py` — DI wiring for current and future repository implementations
- `src/presentation/http/` and `src/infrastructure/health.py` — current public HTTP surface that must remain stable
- `src/application/services/expense_service.py` and `src/domain/models/expense.py` — current prepare/commit boundary already shared by Telegram and HTTP flows
- `docker-compose.yml` and local dev database tooling — current optional PostgreSQL scaffolding that must be reconciled with the chosen runtime approach
- `tests/` — regression coverage plus any new integration coverage
- `docs/ARCHITECTURE.md`, `docs/AI_WORKFLOW.md`, `README.md` — only if implementation finalizes decisions that change project invariants

## Prerequisites (Manual)
- [x] Back up the current SQLite database before any migration work starts.
- [x] Confirm local PostgreSQL is available for development and integration testing. The current Docker `postgres` profile is optional scaffolding, not the full runtime migration by itself.
- [x] Confirm Railway environment constraints assuming the current single-process `APP_MODE=full` deployment and the existing rule that `APP_MODE=http-dev` is not allowed on Railway.

## Implementation Steps
*(Models MUST mark steps with [x] as they are completed and save the file)*

### Group 1
<!-- Lock the missing architecture decisions before code changes. -->

#### [x] Step 1: Record the advisor architecture baseline in an ADR
- **Files:** `docs/adrs/2026-04-12-financial-advisor-architecture-baseline.md`, `docs/ARCHITECTURE.md`
- **Action:** Accepted. Phase 1 starts from the current single-repo, single-public-server runtime. The ADR and architecture doc now capture the preserved runtime facts: Railway public HTTP entrypoint, HTTP-first local development, existing OAuth callback flow, and shared prepare/commit service boundaries.
- **Tests:** N/A — documentation review only

#### [x] Step 2: Record the persistence strategy ADR
- **Files:** `docs/adrs/2026-04-12-financial-advisor-persistence-strategy.md`
- **Action:** Accepted. Phase 1 will migrate from SQLite to PostgreSQL. The ADR records PostgreSQL as required Phase 1 scope while keeping current SQLite behavior as the compatibility baseline until cutover lands.
- **Tests:** N/A — documentation review only

### Group 2 (depends on: Group 1)
<!-- Establish safer boundaries in the current repo before swapping infrastructure. -->

#### [x] Step 3: Inventory the current persistence surface and migration scope
- **Files:** `src/infrastructure/repositories/database_manager.py`, `src/infrastructure/repositories/sqlite_user_repository.py`, `src/infrastructure/repositories/sqlite_learning_repository.py`, `src/infrastructure/repositories/sqlite_split_config_repository.py`, `tests/test_database_manager.py`, `tests/test_sqlite_user_repository.py`, `tests/test_sqlite_learning_repository.py`, `tests/test_sqlite_split_config_repository.py`
- **Action:** Completed. The current SQLite baseline and PostgreSQL compatibility checklist are now captured below so later groups can implement against an explicit target instead of rediscovering behavior from code.
- **Tests:** Existing SQLite repository tests remain green and become the behavioral baseline for later groups

**Current SQLite baseline**

- `DatabaseManager` owns the full runtime schema and versioned migration history. The active baseline is schema version `9`.
- `DatabaseManager.get_connection()` returns one lazily created runtime connection per thread. Migration/startup uses a dedicated initialization connection.
- `user_configurations` is the primary per-user table. Current persisted fields include:
  `telegram_id`, `status`, `budget_id`, `default_account_id`, `default_account_name`, `username`, `first_name`, `last_name`, `created_at`, `updated_at`, `approved_at`, `approved_by`, `ynab_access_token`, `ynab_refresh_token`, `ynab_token_expires_at`, `timezone`, `last_weekly_summary_sent`, `confirm_before_create`.
- `payee_category_mappings` stores learned category mappings keyed by `(telegram_id, normalized_payee, category_id)` with a mutable `count` and `category_name`.
- `user_corrections` stores correction history per user.
- `recent_transactions` stores recent expense history per user and trims to the latest `20` rows per user after each insert.
- `split_groups` stores per-user split categories with uniqueness on `(telegram_id, category_id)`.
- `split_person_aliases` stores aliases per split group with uniqueness on `(split_group_id, alias)` and cascade delete from `split_groups`.
- `split_shared_account` stores one shared tracking account per user keyed by `telegram_id`.

**Behavioral compatibility checklist for PostgreSQL cutover**

- Preserve per-user isolation in every query and uniqueness constraint. No repository method may return or mutate cross-user data.
- Preserve `SQLiteUserRepository.save()` upsert behavior:
  insert-or-update by `telegram_id`, update mutable fields, and preserve the original `created_at` value on updates.
- Preserve token-at-rest handling at the repository boundary:
  encrypted values are stored, decrypted values are returned to the domain model.
- Preserve timezone default behavior:
  missing persisted timezone resolves to `DEFAULT_TIMEZONE` (`America/Bogota`) at load time.
- Preserve boolean semantics for `confirm_before_create`, including default `False` and round-trip behavior through persistence.
- Preserve nullable datetime semantics for `approved_at`, `ynab_token_expires_at`, and `last_weekly_summary_sent`.
- Preserve learning write patterns:
  successful transactions increment existing `(telegram_id, normalized_payee, category_id)` mappings instead of creating duplicates.
- Preserve correction behavior:
  user corrections decrement the old mapping, delete rows whose count reaches zero, and upsert the new mapping.
- Preserve prediction behavior:
  `predict_category()` returns `None` when no mapping exists or when the learned category is no longer present in the caller-supplied YNAB categories.
- Preserve recent-transaction behavior:
  inserts retain newest-first retrieval ordering and enforce the per-user cap of `20` rows.
- Preserve split-config behavior:
  adding the same split group twice must remain idempotent from the caller perspective, and deleting a split group must remove its aliases.
- Preserve case-insensitive alias lookup semantics in `find_split_group_by_alias()`.
- Preserve shared-account upsert behavior keyed by `telegram_id`.
- Preserve error translation at repository boundaries:
  persistence failures still surface as project-level exceptions, not raw driver exceptions leaking into services.

**Test baseline that PostgreSQL repositories must satisfy**

- `tests/test_database_manager.py` currently defines the schema and migration baseline at version `9`; the PostgreSQL foundation needs an equivalent migration/version test surface.
- `tests/test_sqlite_user_repository.py` defines the expected user persistence contract, especially upsert, timestamp preservation, timezone defaulting, and confirmation-mode persistence.
- `tests/test_sqlite_learning_repository.py` defines the expected learning contract, especially per-user isolation, correction semantics, category prediction, and recent-transaction trimming.
- `tests/test_sqlite_split_config_repository.py` defines the split-config contract, especially duplicate-group idempotency, alias operations, cascade delete, case-insensitive alias lookup, shared-account upsert, and per-user isolation.

#### [x] Step 4: Stabilize application boundaries for future advisor reuse
- **Files:** `src/domain/`, `src/application/services/`, `src/presentation/http/`, `main.py`, `tests/conftest.py`
- **Action:** Completed. Reduced packaging and import shortcuts without changing repo layout or runtime behavior. The current public HTTP API, its request-validation/auth boundary, the `PreparedExpense`-based prepare/commit flow, and Telegram runtime behavior remain unchanged.
- **Tests:** `tests/test_main.py`, `tests/test_http_server.py`, `tests/test_health.py`, `tests/test_http_auth.py`, `tests/test_expense_api_handler.py`, and representative service tests pass without import regressions

**Progress note**

- The DI container now resolves service dependencies through repository interfaces (`UserRepository`, `LearningRepository`, `SplitConfigRepository`) instead of binding services directly to SQLite concrete classes. This keeps current behavior unchanged while making the later PostgreSQL swap a wiring change instead of a service-constructor refactor.
- Runtime/test import bootstrap is now centralized through `project_bootstrap.py` instead of duplicated `sys.path` mutations scattered across `main.py` and individual test modules. The repo still uses the current root-plus-`src/` layout, but the bootstrap shortcut is now explicit and shared.
- Test imports that previously mixed `src.*` and package-root imports now follow the same package-root boundary as the runtime, reducing ambiguity about the active module path during future persistence work.

### Group 3 (depends on: Group 2)
<!-- Introduce the new persistence foundation without cutting over runtime yet. -->

#### [x] Step 5: Add the selected persistence foundation
- **Files:** `requirements.txt`, `src/infrastructure/config/app_config.py`, new persistence support files under `src/infrastructure/repositories/` or another ADR-approved location
- **Action:** Completed. Added PostgreSQL dependency and non-cutover foundation support:
  `PERSISTENCE_BACKEND` / `POSTGRES_DSN` config handling in `AppConfig`, a migration-capable `PostgresDatabaseManager`, and the initial PostgreSQL baseline schema derived from the current SQLite v9 runtime contract. The active runtime still remains on SQLite until later cutover steps.
- **Tests:** Configuration tests cover new required settings; new infrastructure unit tests validate connection lifecycle and error handling

#### [x] Step 6: Create migration and integration test scaffolding
- **Files:** `tests/`, migration tooling files, optional local compose/dev files if required by the chosen strategy
- **Action:** Completed. Added a reusable SQLite-to-PostgreSQL migration helper plus a local script entrypoint, an opt-in PostgreSQL integration smoke test gated by `POSTGRES_INTEGRATION_DSN`, and local DX documentation for bringing up the Docker PostgreSQL profile and exercising the migration scaffold.
- **Tests:** New integration setup proves the target schema can be created and exercised in tests

### Group 4 (depends on: Group 3)
<!-- Swap repository implementations behind the existing application interfaces. -->

#### [x] Step 7: Implement replacement repositories behind existing interfaces
- **Files:** New repository implementations under `src/infrastructure/repositories/`, related tests under `tests/`
- **Action:** Completed. Added PostgreSQL-backed user, learning, and split-config repository implementations behind the existing repository ABCs. The current runtime still remains on SQLite; these repositories are implemented and verified but not yet wired into the container/runtime.
- **Tests:** Repository-focused contract tests cover the new PostgreSQL implementations, and the PostgreSQL foundation/integration scaffold from Step 6 remains available for opt-in environment-backed verification

#### [x] Step 8: Wire the new persistence layer into the container without breaking current surfaces
- **Files:** `src/infrastructure/container.py`, `main.py`, `src/presentation/http/`, `src/infrastructure/health.py`
- **Action:** Completed. The DI container now selects SQLite or PostgreSQL persistence from `PERSISTENCE_BACKEND`. SQLite remains the default path; PostgreSQL initialization and repository wiring activate only when configured. Telegram behavior, OAuth callback handling, health routing, and the authenticated HTTP expense endpoint remain on the same service/runtime boundaries.
- **Tests:** Runtime-facing tests covering container wiring, bot initialization, health/OAuth routing, and HTTP expense handling pass after the backend-selection cutover

### Group 5 (depends on: Group 4)
<!-- Remove obsolete SQLite code only after the new path is validated. -->

#### [x] Step 9: Remove deprecated SQLite-only runtime code
- **Files:** Obsolete SQLite runtime files, configuration docs, migration references, and tests that are no longer valid after cutover
- **Action:** Delete or archive SQLite-only runtime paths only after the new persistence layer is verified. Keep any one-time migration tooling needed for rollback or audit outside the runtime path.
- **Tests:** Full test suite passes and targeted searches confirm stale runtime references are gone

**Progress note**

- Runtime configuration now defaults to PostgreSQL instead of SQLite. New `AppConfig.from_env()` loads now require `POSTGRES_DSN` unless callers explicitly opt into the temporary SQLite compatibility path.
- The DI container runtime path is now PostgreSQL-only; backend switching for SQLite has been removed from application startup. Remaining SQLite usage is limited to migration tooling, direct repository compatibility tests, and other non-runtime support paths.
- Step 9 is not complete until the remaining stale docs/config references and any obsolete SQLite runtime artifacts are removed or archived.

#### [x] Step 10: Update project documentation and rollout notes
- **Files:** `docs/ARCHITECTURE.md`, `README.md`, `docs/wip_state.md`, and any relevant ADR references
- **Action:** Update architecture and operational docs to match the implemented foundations. Document rollout steps, rollback expectations, and what later advisor phases can now assume.
- **Tests:** N/A — documentation review only

**Progress note**

- `README.md`, `docs/ARCHITECTURE.md`, `docs/dev/README.md`, and `config/.env.dev.example` now describe PostgreSQL as the runtime persistence baseline instead of SQLite.
- `docs/dev/railway-postgres-cutover.md` now documents the intended Railway migration order: freeze writes, back up SQLite, copy into PostgreSQL, validate, cut over, and keep the SQLite backup for rollback.
- SQLite is now documented as migration/compatibility support only.
- Final rollout notes, rollback guidance, and handoff state now match the completed PostgreSQL cutover.

## Constraints & Architecture
- The plan must preserve current user-facing bot behavior and all Spanish UI strings.
- The existing public HTTP server on Railway remains a protected surface throughout Phase 1.
- Per-user isolation and YNAB milliunit rules remain unchanged.
- The plan must not assume a `bot/api/web/shared` monorepo split unless a separate ADR explicitly approves it.
- The plan must preserve the current authenticated HTTP contract, including strict request validation, constant-time bearer token checks, and the shared prepare/commit service flow used by Telegram and HTTP.
- PostgreSQL migration is required Phase 1 scope, not an optional future branch.
- If Phase 1 changes the database layer away from `DatabaseManager`, the corresponding invariant docs must be updated in the same implementation stream.
- New persistence work must have real regression coverage before SQLite runtime code is removed.

## Verification
- [x] Existing Telegram bot flows still work after each cutover step.
- [x] The current authenticated HTTP expense endpoint still works on the public server.
- [x] HTTP auth, request validation, and preview/commit behavior remain covered by targeted tests after any boundary refactor.
- [x] The chosen persistence strategy has automated test coverage and a documented migration path.
- [x] Documentation and ADRs match the implementation that Phase 1 actually ships.
- [x] Phase 2 work can start from these foundations without needing to rediscover repo layout, runtime entrypoints, or persistence assumptions.
