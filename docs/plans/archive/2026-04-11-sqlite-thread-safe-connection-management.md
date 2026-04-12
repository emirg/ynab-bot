# Plan: SQLite Thread-Safe Connection Management

## Objective & Context
- **Status:** Completed
- **Source Spec:** `docs/specs/2026-04-11-sqlite-thread-safe-connection-management.md`
- **Goal:** Remove unsafe cross-thread SQLite connection sharing while preserving repository and service interfaces.
- **Approach:** Refactor `DatabaseManager` to own a dedicated migration connection plus lazily-created thread-local runtime connections, then verify repository compatibility with targeted tests.

## Affected Components
- `src/infrastructure/repositories/database_manager.py` — implement per-thread connection management and cleanup
- `tests/test_database_manager.py` — add migration and thread-local connection assertions
- `tests/test_sqlite_user_repository.py` — verify repository behavior remains stable after the manager change

## Prerequisites (Manual)
- [ ] None

## Implementation Steps

### Group 1
<!-- Introduce the new connection-management model -->

#### [x] Step 1: Refactor DatabaseManager connection ownership
- **Files:** `src/infrastructure/repositories/database_manager.py`
- **Action:** Replace the single shared runtime connection with a dedicated initialization connection plus thread-local runtime connections; apply row factory and pragmas to every new connection; close all tracked connections safely.
- **Tests:** `tests/test_database_manager.py` — add a scenario asserting separate threads receive separate connection objects and keep migration behavior intact.

### Group 2 (depends on: Group 1)
<!-- Validate existing repository behavior against the new manager -->

#### [x] Step 2: Verify repository compatibility
- **Files:** `tests/test_sqlite_user_repository.py`
- **Action:** Add or adjust repository tests only where needed to prove normal save/read behavior still works with the new manager contract.
- **Tests:** `tests/test_sqlite_user_repository.py` — preserve current CRUD expectations after the manager refactor.

## Constraints & Architecture
- `DatabaseManager` remains the single database entry point.
- Migrations stay centralized and automatic.
- Repository interfaces and service call sites must not change.
- Preserve project invariants: per-user isolation and database safety.
- This plan is governed by ADR `docs/adrs/2026-04-11-sqlite-per-thread-connections.md`.

## Verification
- [x] Run `.venv/bin/pytest tests/test_database_manager.py tests/test_sqlite_user_repository.py`
- [x] Run `.venv/bin/pytest tests/test_http_server.py tests/test_health.py tests/test_main.py`
