# Spec: SQLite Thread-Safe Connection Management

## Metadata
- **Status:** Implemented
- **Owner:** Codex
- **Related Roadmap Item:** None
- **Related ADRs:** `docs/adrs/2026-04-11-sqlite-per-thread-connections.md`

## Summary
The current persistence layer shares a single SQLite connection across repositories and runtime threads. This refactor changes connection ownership so each thread receives its own connection while preserving the existing repository interfaces and migration flow. The goal is to remove unsafe cross-thread access without changing domain behavior.

## Problem
- `DatabaseManager` currently stores a single process-wide `sqlite3.Connection`.
- The application serves work from at least two runtime threads: the public HTTP server and the Telegram runtime.
- Sharing one connection with `check_same_thread=False` increases the risk of concurrency bugs, transaction interference, and hard-to-debug SQLite failures.

## Goals
- Eliminate process-wide shared SQLite connection usage.
- Preserve current repository method signatures and service call sites.
- Keep migrations centralized and automatically applied at startup.
- Keep user-scoped queries and existing domain behavior unchanged.

## Non-Goals
- Replacing SQLite with another database.
- Redesigning repository contracts or service orchestration.
- Changing persisted schema or business rules.

## Users / Consumers
- Application runtime threads using SQLite repositories.
- Future maintainers who rely on stable repository interfaces.

## Expected Behavior
- Runtime code retrieves a connection through `DatabaseManager`, but the returned connection belongs to the current thread instead of the whole process.
- Migrations still execute automatically during startup before normal repository traffic.
- Repository behavior remains the same from the perspective of services and handlers.
- Shutdown or explicit cleanup closes all connections managed by `DatabaseManager`.

## Inputs and Outputs
- **Inputs:** Repository calls to `DatabaseManager.get_connection()`, application startup, application shutdown.
- **Outputs:** Thread-local SQLite connections, applied migrations, committed reads and writes using the current thread's connection.
- **Public Interfaces:** Internal persistence contract of `DatabaseManager.get_connection()`.

## Business Rules and Constraints
- The `DatabaseManager` remains the central database layer.
- Migrations remain versioned and automatic.
- Per-user isolation rules remain unchanged.
- No new singleton repository state may depend on sharing one SQLite connection object.

## Edge Cases and Failure Handling
- If a thread accesses the database for the first time after startup, its connection must be initialized with the required pragmas and row factory.
- If migration initialization fails, startup must still fail fast with `YNABBotException`.
- Explicit cleanup must remain safe even if some threads have not opened a connection.

## Acceptance Criteria
- [ ] Different runtime threads do not share the same SQLite connection object.
- [ ] Startup still migrates a fresh database to the latest schema version.
- [ ] Existing repository tests continue to pass without service-level contract changes.
- [ ] A dedicated test proves thread-local connection behavior.

## Open Questions
- None

## References
- `docs/AI_WORKFLOW.md`
- `src/infrastructure/repositories/database_manager.py`
- `src/infrastructure/container.py`
- `src/infrastructure/health.py`
- `main.py`
