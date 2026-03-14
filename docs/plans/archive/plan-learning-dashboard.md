# Plan: Learning Dashboard (Milestone 1.2)

## Objective & Context
- **Status:** Complete
- **Goal:** Add `/aprendizaje` command showing learned payee-category associations with frequency, `/olvidar <payee>` to delete incorrect associations, and improve `/stats` with more actionable information.
- **Why:** Users have no visibility into what the bot has learned from their expenses. They cannot remove incorrect associations, and `/stats` shows abstract metrics without actionable insight.

## Prerequisites (Manual)
- [x] None. All infrastructure (SQLite learning tables, DI wiring, LearningHandler) already exists.

## Implementation Steps
*(Models MUST mark steps with [x] as they are completed and save the file)*

### [x] Step 1: Add `get_payee_associations` to LearningRepository interface
- **Files:** `src/domain/repositories/learning_repository.py`
- **Action:** Add abstract method `get_payee_associations(self, telegram_id: int) -> List[Dict]` that returns all payee-category mappings for a user. Each dict should contain: `normalized_payee`, `category_id`, `count`. Results ordered by `count DESC`.
- **Tests:** No tests needed for abstract interface — covered by implementation tests in Step 3.

### [x] Step 2: Add `delete_payee_associations` to LearningRepository interface
- **Files:** `src/domain/repositories/learning_repository.py`
- **Action:** Add abstract method `delete_payee_associations(self, telegram_id: int, normalized_payee: str) -> int` that deletes all associations for a given payee for a user. Returns the number of rows deleted. This enables the `/olvidar` command.
- **Tests:** No tests needed for abstract interface — covered by implementation tests in Step 3.

### [x] Step 3: Implement both methods in SQLiteLearningRepository
- **Files:** `src/infrastructure/repositories/sqlite_learning_repository.py`
- **Action:**
  - `get_payee_associations`: Query `payee_category_mappings` for the user, ordered by `count DESC`. Return list of dicts with `normalized_payee`, `category_id`, `count`.
  - `delete_payee_associations`: Delete all rows from `payee_category_mappings` WHERE `telegram_id = ? AND normalized_payee = ?`. Use `normalize_payee()` on the input to match stored data. Return `cursor.rowcount`. Commit after delete.
- **Tests:** `tests/test_sqlite_learning_repository.py`
  - Test `get_payee_associations` returns correct data sorted by count DESC
  - Test `get_payee_associations` returns empty list for user with no data
  - Test `get_payee_associations` respects per-user isolation (user A cannot see user B data)
  - Test `delete_payee_associations` removes all mappings for a payee
  - Test `delete_payee_associations` returns 0 when payee not found
  - Test `delete_payee_associations` does not affect other payees or other users

### [x] Step 4: Add service methods to LearningService
- **Files:** `src/application/services/learning_service.py`
- **Action:**
  - Add `get_payee_associations(self, telegram_id: int) -> List[Dict]` — delegates to repository.
  - Add `forget_payee(self, telegram_id: int, payee: str) -> bool` — calls `normalize_payee(payee)` then `delete_payee_associations`. Returns `True` if rows were deleted, `False` otherwise. Log the action.
  - Add `format_learning_dashboard_message(self, telegram_id: int) -> str` — builds the `/aprendizaje` response message. Groups by payee, shows the most-used category for each payee with its count. Format: "McDonald's -> Restaurantes (7 veces)". For old rows without `category_name` (empty string), display "Categoria desconocida" as fallback. If no associations exist, return a friendly empty-state message. Limit display to top 20 payees to avoid message overflow.
  - Add `format_forget_result_message(self, payee: str, success: bool) -> str` — returns Spanish success/failure message for `/olvidar`.
- **Tests:** `tests/test_learning_service.py`
  - Test `get_payee_associations` delegates correctly
  - Test `forget_payee` returns True when associations exist
  - Test `forget_payee` returns False when payee not found
  - Test `format_learning_dashboard_message` with associations (verify format)
  - Test `format_learning_dashboard_message` with empty data (verify empty state)
  - Test `format_learning_dashboard_message` with missing category_name shows "Categoria desconocida" fallback
  - Test `format_forget_result_message` success case
  - Test `format_forget_result_message` failure case

### [x] Step 5: Enhance `format_statistics_message` in LearningService
- **Files:** `src/application/services/learning_service.py`
- **Action:** Improve the existing `/stats` message to include more actionable information:
  - Add "Top 3 comercios mas frecuentes" with their counts
  - Add "Categorias mas usadas" (top 3) with transaction counts
  - Keep existing metrics but reformat for clarity
  - To get this data, add a helper method `_get_top_payees(self, telegram_id: int, limit: int = 3) -> List[Dict]` and `_get_top_categories(self, telegram_id: int, limit: int = 3) -> List[Dict]` that query through the repository's `get_payee_associations`.
- **Tests:** `tests/test_learning_service.py`
  - Test enhanced stats message contains top payees section
  - Test enhanced stats message contains top categories section
  - Test stats message with no data still renders correctly (no crash on empty)

### [x] Step 6: Add `category_name` column via migration v4
- **Files:** `src/infrastructure/repositories/database_manager.py`, `src/infrastructure/repositories/sqlite_learning_repository.py`
- **Design decision (RESOLVED):** The `payee_category_mappings` table stores `category_id` but the dashboard needs category *names*. We add `category_name` via migration v4. No YNAB API backfill for old rows -- old rows will display "Categoria desconocida" as fallback. A future DB reset is likely, making this a non-issue long term.
- **Action:**
  - Add migration v4 in `database_manager.py`: `ALTER TABLE payee_category_mappings ADD COLUMN category_name TEXT DEFAULT '';`
  - Update `record_successful_transaction` to also store `expense.category_name` in the new column. Use `ON CONFLICT ... DO UPDATE SET count = count + 1, last_updated = ..., category_name = excluded.category_name` so the name stays current.
  - Update `get_payee_associations` to include `category_name` in its returned dicts.
- **Tests:** `tests/test_sqlite_learning_repository.py`
  - Test `record_successful_transaction` stores category_name
  - Test `get_payee_associations` returns category_name
  - Test migration v4 applies cleanly (existing `test_database_manager.py` pattern)

**Note on ordering:** Step 6 adds a migration that Steps 4-5 depend on for category names. The executor should implement Step 6 BEFORE Step 4-5, or implement them together. Steps are numbered for logical grouping, but the executor should apply Step 6's migration and repository changes first, then build the service layer on top.

### [x] Step 7: Add `/aprendizaje` and `/olvidar` handlers to LearningHandler
- **Files:** `src/presentation/telegram/handlers/learning_handler.py`
- **Action:**
  - Add `handle_learning_dashboard_command` — calls `learning_service.format_learning_dashboard_message(user_id)` and sends the result. Decorated with `@require_authentication`.
  - Add `handle_forget_command` — parses payee from `context.args` (joined as a single string), calls `learning_service.forget_payee(user_id, payee)`, sends result via `learning_service.format_forget_result_message`. If no args, send usage help in Spanish. Decorated with `@require_authentication`.
  - Update `handle()` method to route `/aprendizaje` and `/olvidar` commands.
- **Tests:** `tests/test_learning_handler.py` (create if not exists, or add to existing)
  - Test `/aprendizaje` calls service and sends formatted message
  - Test `/olvidar payee_name` calls forget_payee with correct normalized payee
  - Test `/olvidar` with no args sends usage help
  - Test both commands require authentication

### [x] Step 8: Register new commands in bot.py
- **Files:** `src/presentation/telegram/bot.py`
- **Action:**
  - Add `CommandHandler("aprendizaje", self.learning_handler.handle_learning_dashboard_command)` in the "Learning system commands" section.
  - Add `CommandHandler("olvidar", self.learning_handler.handle_forget_command)` in the same section.
- **Tests:** No separate tests needed — covered by handler tests in Step 7 and existing bot initialization tests.

### [x] Step 9: Update formatters and help text
- **Files:** `src/presentation/telegram/formatters.py`
- **Action:**
  - Add `/aprendizaje` and `/olvidar` to `format_command_list()` under the "Aprendizaje" section.
  - Add `/aprendizaje` to `format_welcome_message()` command list if applicable.
  - Add `format_learning_dashboard_response` and `format_forget_response` static methods to `LearningResponseFormatter` if any presentation-layer formatting is needed beyond what the service provides. Otherwise, the service methods from Step 4 handle formatting directly (current pattern: `format_statistics_message` lives in the service, not the formatter).
- **Tests:** `tests/test_formatters.py` (if exists) — verify new commands appear in help text.

### [x] Step 10: Integration verification
- **Files:** No new files
- **Action:**
  - Run full test suite: `pytest` — all tests must pass
  - Verify coverage stays at ~86%+
  - Manual smoke test: `/aprendizaje` with existing learning data, `/olvidar` with a known payee, `/stats` shows enhanced output

## Constraints & Architecture
- All user-facing strings in Spanish (per ARCHITECTURE.md)
- Per-user data isolation: all queries scoped by `telegram_id`
- DI pattern: `LearningService` resolved via `container.get(LearningService)` — no direct repository access from handlers
- Migration v4 must be additive (ALTER TABLE ADD COLUMN) — no destructive changes
- `normalize_payee()` must be used consistently when matching/deleting payees (the `/olvidar` command input must go through normalization before querying)
- No breaking changes to existing expense recording flow — `record_successful_transaction` gains a column but the ON CONFLICT clause handles backward compatibility
- Old rows without `category_name` (pre-migration) display "Categoria desconocida" as fallback. No YNAB API backfill needed -- a DB reset is likely in the near future, making this a non-issue long term

## Execution Order Recommendation
The logical step numbering groups by layer, but the recommended execution order is:
1. Steps 1-2 (repository interface)
2. Step 6 (migration + repository implementation for category_name)
3. Step 3 (repository implementation of new methods)
4. Steps 4-5 (service layer)
5. Steps 7-8 (presentation layer)
6. Step 9 (help text updates)
7. Step 10 (verification)

## Verification
- [x] `/aprendizaje` shows list of learned payee-category associations with counts
- [x] `/aprendizaje` shows friendly message when no associations exist
- [x] `/olvidar McDonald's` removes all McDonald's associations and confirms
- [x] `/olvidar` with no args shows usage help
- [x] `/stats` shows top payees and top categories sections
- [x] All existing tests pass (no regressions)
- [x] New tests cover all new methods
- [x] Coverage remains at ~86%+

## Review
- **Reviewed by:** Claude Code (Lead Architect)
- **Date:** 2026-03-14
- **Verdict:** Approved. All invariants satisfied (per-user isolation, normalize_payee consistency, Spanish UI, DI pattern, migration safety, category_name fallback).
