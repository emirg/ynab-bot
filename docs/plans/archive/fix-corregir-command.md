# Plan: Fix /corregir Command (3 Bugs)

## Objective & Context
- **Status:** Completed
- **Harness Roadmap Marker:** 3.1
- **Goal:** Fix three bugs in the `/corregir` command: (1) category name not resolved to YNAB UUID, (2) `category_name` not saved in correction records, (3) YNAB transaction not updated with the new category.
- **Why:** Currently `/corregir` only saves the raw user string as `category_id` (not a UUID), doesn't persist `category_name` (causing "Categoria desconocida" in `/aprendizaje`), and never updates the actual YNAB transaction — leaving it with the old category.

## Affected Components
- `src/domain/repositories/ynab_repository.py` — add `update_transaction_category()` abstract method
- `src/infrastructure/repositories/ynab_api_repository.py` — implement `update_transaction_category()` via YNAB PUT API
- `src/domain/repositories/learning_repository.py` — update `record_user_correction` signature to accept `new_category_name`, update `add_recent_transaction` signature to accept optional `ynab_transaction_id`
- `src/infrastructure/repositories/sqlite_learning_repository.py` — store `category_name` in correction INSERT, store `ynab_transaction_id` in `add_recent_transaction`, update `get_recent_transactions` to return it
- `src/infrastructure/repositories/database_manager.py` — migration v6: add `ynab_transaction_id` column to `recent_transactions`
- `src/application/services/expense_service.py` — rewrite `correct_recent_transaction()` to resolve category via fuzzy match, update YNAB transaction, pass `category_name` to repository, also update `_process_parsed_expense` and siblings to pass `transaction_id` to `add_recent_transaction`
- `src/presentation/telegram/handlers/learning_handler.py` — display resolved category name (not raw user input) in success message
- Tests: `tests/test_expense_service.py`, `tests/test_learning_handler.py`, `tests/test_sqlite_learning_repository.py`, `tests/test_ynab_api_repository.py`

## Prerequisites (Manual)
- None

## Implementation Steps

### Group 1: DB Migration + Domain Interfaces
<!-- Add ynab_transaction_id column and update abstract interfaces -->

#### [x] Step 1: Add migration v6 — `ynab_transaction_id` column on `recent_transactions`
- **Files:** `src/infrastructure/repositories/database_manager.py`
- **Action:** Add migration v6 to `_MIGRATIONS` list: `ALTER TABLE recent_transactions ADD COLUMN ynab_transaction_id TEXT;`. This column stores the YNAB transaction ID returned from `create_transaction`, enabling the correction flow to update the transaction in YNAB later.
- **Tests:** `tests/test_database_manager.py` — verify migration v6 applies cleanly and the column exists (follow existing migration test patterns).

#### [x] Step 2: Add `update_transaction_category()` to `YNABRepository` interface
- **Files:** `src/domain/repositories/ynab_repository.py`
- **Action:** Add abstract method `update_transaction_category(self, budget_id: str, transaction_id: str, category_id: str) -> bool`. Returns `True` on success, `False` on failure.
- **Tests:** No direct tests needed (abstract interface).

#### [x] Step 3: Update `LearningRepository` interface — `record_user_correction` and `add_recent_transaction`
- **Files:** `src/domain/repositories/learning_repository.py`
- **Action:**
  - Change `record_user_correction` signature to: `record_user_correction(self, telegram_id: int, payee: str, old_category_id: str, new_category_id: str, new_category_name: str = "") -> None`
  - Change `add_recent_transaction` signature to: `add_recent_transaction(self, telegram_id: int, expense: Expense, ynab_transaction_id: str = None) -> None`
- **Tests:** No direct tests needed (abstract interface).

### Group 2: Infrastructure Implementations (depends on: Group 1)
<!-- Implement the concrete changes in repositories -->

#### [x] Step 4: Implement `update_transaction_category()` in `YNABApiRepository`
- **Files:** `src/infrastructure/repositories/ynab_api_repository.py`
- **Action:** Implement `update_transaction_category(self, budget_id, transaction_id, category_id)` using `PUT /budgets/{budget_id}/transactions/{transaction_id}` with JSON body `{"transaction": {"category_id": category_id}}`. Return `True` on 200/201, `False` on error. Log errors but don't raise — the correction should still save the learning even if the YNAB update fails.
- **Tests:** `tests/test_ynab_api_repository.py` — test successful update (mock 200 response), test failed update (mock 4xx), test request exception handling.

#### [x] Step 5: Update `SQLiteLearningRepository` — save `category_name` in corrections + `ynab_transaction_id` in recent transactions
- **Files:** `src/infrastructure/repositories/sqlite_learning_repository.py`
- **Action:**
  1. Update `record_user_correction` to accept `new_category_name: str = ""` parameter. In the `INSERT INTO payee_category_mappings` for the new category (the "increase new category count" block at the bottom), add `category_name = excluded.category_name` to the `ON CONFLICT DO UPDATE` clause, and pass `new_category_name` in the VALUES. This fixes bug #2.
  2. Update `add_recent_transaction` to accept `ynab_transaction_id: str = None`. Add it to the INSERT statement for `recent_transactions`.
  3. Update `get_recent_transactions` to also SELECT and return `ynab_transaction_id` in the result dict.
- **Tests:** `tests/test_sqlite_learning_repository.py` — test that `record_user_correction` with `new_category_name` persists the name in `payee_category_mappings`, test that `add_recent_transaction` stores and retrieves `ynab_transaction_id`.

### Group 3: Service Layer (depends on: Group 2)
<!-- Fix the core business logic in ExpenseService -->

#### [x] Step 6: Rewrite `correct_recent_transaction()` in `ExpenseService`
- **Files:** `src/application/services/expense_service.py`
- **Action:** Rewrite `correct_recent_transaction(self, telegram_user_id, transaction_index, new_category_input)`:
  1. Get user config and YNAB repository (existing pattern).
  2. Load categories from YNAB via `ynab_repository.get_categories()`.
  3. Call `_update_llm_parser_data(categories, ...)` to populate lookup maps.
  4. Resolve `new_category_input` to a real category via `_find_category_id_by_name(new_category_input, categories)`.
  5. If no match found, return a dict with `error` key: `{"error": f"No encontre una categoria que coincida con '{new_category_input}'. Verifica el nombre e intenta de nuevo."}`.
  6. Find the resolved category name by looking up the category object from the categories list.
  7. Get recent transactions from learning repo.
  8. Validate transaction index.
  9. If the transaction has a `ynab_transaction_id`, call `ynab_repository.update_transaction_category(budget_id, ynab_transaction_id, resolved_category_id)`. Log but don't fail if this returns `False`.
  10. Call `self.learning_repository.record_user_correction(telegram_user_id, payee, old_category_id, resolved_category_id, resolved_category_name)`.
  11. Return `{'payee': payee, 'old_category_name': old_category_name, 'new_category_name': resolved_category_name, 'ynab_updated': bool}`.
- **Tests:** `tests/test_expense_service.py` — update `TestCorrectRecentTransaction`:
  - Test successful correction resolves category name to UUID via fuzzy match.
  - Test category not found returns error dict.
  - Test YNAB transaction is updated when `ynab_transaction_id` is present.
  - Test YNAB update failure still saves learning correction.
  - Test `new_category_name` is passed to `record_user_correction`.

#### [x] Step 7: Update all `add_recent_transaction` call sites to pass `transaction_id`
- **Files:** `src/application/services/expense_service.py`
- **Action:** In `_process_parsed_expense`, `_process_shared_expense`, `process_receipt_image`, and `process_expense_message`: change `self.learning_repository.add_recent_transaction(telegram_user_id, expense)` to `self.learning_repository.add_recent_transaction(telegram_user_id, expense, transaction_id)` where `transaction_id` is the value returned by `ynab_repository.create_transaction()`.
- **Tests:** `tests/test_expense_service.py` — verify that existing tests still pass (the `transaction_id` is already returned and available in scope). Add an assertion in one representative test that `add_recent_transaction` is called with the third argument.

### Group 4: Handler Layer (depends on: Group 3)
<!-- Update the handler to use resolved category name and handle errors -->

#### [x] Step 8: Update `handle_correction_command` in `LearningHandler`
- **Files:** `src/presentation/telegram/handlers/learning_handler.py`
- **Action:**
  1. After calling `correct_recent_transaction`, check if result contains an `error` key. If so, send the error message to the user and return.
  2. On success, use `result['new_category_name']` (the resolved name) instead of the raw `new_category_id` user input when calling `format_correction_success`.
  3. If `result.get('ynab_updated')` is True, optionally append a note like "La transaccion en YNAB tambien fue actualizada." to the response, or incorporate it into the formatter.
- **Tests:** `tests/test_learning_handler.py` — add tests for `handle_correction_command`:
  - Test successful correction shows resolved category name.
  - Test category-not-found error shows user-friendly message.
  - Test missing arguments shows help message.
  - Test invalid transaction number shows error.

## Constraints & Architecture
- **Fuzzy matching:** Reuse `_find_category_id_by_name()` which already implements 4-tier matching (exact -> full_name -> case-insensitive -> partial -> clean/no-emoji). This requires calling `_update_llm_parser_data()` first to populate the lookup maps.
- **YNAB API update:** The YNAB v1 API supports `PUT /budgets/{budget_id}/transactions/{transaction_id}` with a `transaction` payload. Only send `category_id` in the update body.
- **Graceful degradation:** If the YNAB API update fails (network error, token expired, etc.), the correction should still be saved locally for learning. The user should be informed the YNAB update failed but learning was saved.
- **`category_name` in `record_user_correction`:** The new parameter is optional with default `""` to maintain backward compatibility with any existing callers or test mocks.
- **DB migration safety:** Adding a nullable column via ALTER TABLE is safe and doesn't require data migration. Existing rows will have `NULL` for `ynab_transaction_id`, which the correction flow handles gracefully (it just skips the YNAB update).
- **Corrupted data:** Existing corrections that stored raw strings as `category_id` will remain in `user_corrections` and `payee_category_mappings`. Since a DB reset is planned (see agent memory), no data migration is needed. The `predict_category` method already verifies the category still exists in YNAB before using it, so stale/invalid category IDs are safely ignored.
- **Per-user isolation:** All operations remain scoped to `telegram_user_id`. The YNAB repository is created per-user via `YNABRepositoryFactory`.
- **UI language:** All user-facing messages in Spanish.

## Verification
- [x] `/corregir 1 groceries` resolves "groceries" to the real YNAB category (e.g., "Groceries") and shows the resolved name
- [x] `/corregir 1 nonexistent` shows a friendly error message about no matching category
- [x] After correction, `/aprendizaje` shows the correct category name (not "Categoria desconocida")
- [x] The YNAB transaction is updated with the new category (verify in YNAB app)
- [x] If YNAB API is unreachable, correction still saves locally and user is informed
- [x] All existing tests pass, new tests cover the three bug fixes
