# ADR: Use Per-Thread SQLite Connections In DatabaseManager

## Metadata
- **Status:** Accepted
- **Date:** 2026-04-11
- **Related Spec:** `docs/specs/2026-04-11-sqlite-thread-safe-connection-management.md`
- **Related Plan:** `docs/plans/archive/2026-04-11-sqlite-thread-safe-connection-management.md`
- **Supersedes:** None
- **Superseded By:** None

## Context
The application currently shares one SQLite connection across singleton repositories and multiple runtime threads. This design relies on `check_same_thread=False` and exposes the process to cross-thread database access risks. The codebase already centralizes connection retrieval through `DatabaseManager`, so a safer ownership model can be introduced without changing repository interfaces.

## Decision
`DatabaseManager` will manage:
- one dedicated initialization connection used during startup and migrations
- one lazily-created runtime connection per thread for normal repository operations

Repositories will continue calling `get_connection()` inside each method. The manager will apply the required SQLite pragmas and row factory to every created connection and will expose safe cleanup for all tracked connections.

## Alternatives Considered
- **Option A:** Keep one global connection with `check_same_thread=False` and rely on SQLite/WAL behavior.
  This was rejected because it preserves the concurrency risk that triggered the refactor.
- **Option B:** Open and close a new connection for every repository method call.
  This was rejected because it adds unnecessary churn and repository noise when the existing repository contract already supports per-thread ownership cleanly.
- **Option C:** Replace SQLite or perform a broader persistence redesign.
  This was rejected because the current issue can be fixed locally without changing domain or repository boundaries.

## Consequences
- **Positive:** Removes unsafe cross-thread connection sharing while preserving repository APIs and service wiring.
- **Positive:** Keeps migration ownership explicit and startup behavior deterministic.
- **Negative:** `DatabaseManager` becomes responsible for tracking multiple runtime connections instead of one.
- **Follow-up:** Maintain concurrency coverage in tests for future persistence changes.

## References
- `src/infrastructure/repositories/database_manager.py`
- `src/infrastructure/container.py`
- `src/infrastructure/health.py`
- `main.py`
