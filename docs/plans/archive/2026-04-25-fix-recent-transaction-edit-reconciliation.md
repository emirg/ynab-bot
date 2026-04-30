# Plan: Fix Recent Transaction Edit Reconciliation

## Objective & Context
- **Status:** Completed
- **Harness Roadmap Marker:** E.10
- **Source Spec:** `docs/specs/archive/2026-04-25-fix-recent-transaction-edit-reconciliation.md`
- **Goal:** Make `/editar` work again for legitimate recent YNAB transactions while preserving safe failure when the local recent reference is truly stale.
- **Approach:** Characterize false stale cases with tests, isolate reconciliation into explicit helpers, loosen only benign comparisons for edit, and keep true missing/stale YNAB states blocked.

## Affected Components
- `src/application/services/expense_service.py` - edit reconciliation and local cache update behavior.
- `src/presentation/telegram/handlers/learning_handler.py` - error mapping review only; likely no behavior change unless service error codes are refined.
- `src/presentation/telegram/formatters.py` - error copy review only if more specific stale reasons are introduced.
- `tests/application/services/test_expense_service.py` - primary service regression coverage.
- `tests/presentation/telegram/test_learning_handler.py` - handler-level error mapping coverage.

## Prerequisites (Manual)
- [x] Capture one failing `/editar` case with the cached recent row and the live YNAB transaction payload, redacting personal details.
- [x] Confirm whether the failing transaction was a normal expense, split transaction, transfer, cleared/reconciled transaction, or manually edited in YNAB.

## Implementation Steps
*(Models MUST mark steps with [x] as they are completed and save the file)*

### Group 1
<!-- Add failing tests that define the intended reconciliation behavior. -->

#### [x] Step 1: Add edit reconciliation false-positive tests
- **Files:** `tests/application/services/test_expense_service.py`
- **Action:** Add tests under `TestEditLastTransaction` for benign live/cache differences that should still allow edit: YNAB payee punctuation/casing, cached amount in major units versus live milliunits, parent transaction with matching subtransaction category, and live transaction containing extra fields such as `date`, `cleared`, or `approved`.
- **Tests:** `.venv/bin/pytest tests/application/services/test_expense_service.py -k "EditLastTransaction and reconcile" -q` should initially expose the false-positive stale behavior for any missing benign case.

#### [x] Step 2: Add true stale guard tests
- **Files:** `tests/application/services/test_expense_service.py`
- **Action:** Add or tighten tests proving edits remain blocked when the live transaction is missing/deleted, while payee/amount/category drift on an existing YNAB transaction no longer blocks `/editar`.
- **Tests:** `.venv/bin/pytest tests/application/services/test_expense_service.py -k "missing_live_ynab_transaction_blocks_edit or live_payee_drift_does_not_block_edit" -q` must pass after implementation.

### Group 2 (depends on: Group 1)
<!-- Refactor reconciliation into readable, testable helpers. -->

#### [x] Step 3: Extract edit reconciliation result helper
- **Files:** `src/application/services/expense_service.py`
- **Action:** Replace the broad `_get_live_transaction_state` comparison logic used by `edit_last_transaction` with `_get_live_transaction_state_for_edit`, which requires the YNAB transaction ID to exist and logs cache drift. Keep `undo_last_transaction` on the stricter `_get_live_transaction_state` path.
- **Tests:** `.venv/bin/pytest tests/application/services/test_expense_service.py -k "EditLastTransaction" -q`.

#### [x] Step 4: Implement tolerant field comparisons
- **Files:** `src/application/services/expense_service.py`
- **Action:** Detect payee, amount, and category drift for logging/cache refresh, but do not return `ynab_transaction_stale` for `/editar` when the YNAB transaction ID still exists. Keep missing IDs and missing live transactions as safe failures.
- **Tests:** `.venv/bin/pytest tests/application/services/test_expense_service.py -k "EditLastTransaction" -q`.

### Group 3 (depends on: Group 2)
<!-- Preserve handler behavior and cache consistency. -->

#### [x] Step 5: Verify local recent cache updates after edit
- **Files:** `src/application/services/expense_service.py`, `tests/application/services/test_expense_service.py`
- **Action:** Ensure `update_recent_transaction` only runs after successful YNAB update and receives edited payee, amount, category id, and category name. Add coverage for a benign-drift successful edit updating the cache.
- **Tests:** `.venv/bin/pytest tests/application/services/test_expense_service.py -k "update_recent_transaction or benign" -q`.

#### [x] Step 6: Review Telegram error mapping
- **Files:** `src/presentation/telegram/handlers/learning_handler.py`, `tests/presentation/telegram/test_learning_handler.py`
- **Action:** Confirm `ynab_transaction_missing` and `ynab_transaction_stale` still map to `format_recent_transaction_sync_error`. If more granular errors are introduced, map them to Spanish copy without leaking raw YNAB payloads.
- **Tests:** `.venv/bin/pytest tests/presentation/telegram/test_learning_handler.py -k "edit_command" -q`.

### Group 4 (depends on: Group 3)
<!-- Final verification. -->

#### [x] Step 7: Run targeted and full test suite
- **Files:** No source edits expected.
- **Action:** Run `.venv/bin/pytest tests/application/services/test_expense_service.py tests/presentation/telegram/test_learning_handler.py -q`, then `.venv/bin/pytest`.
- **Tests:** All targeted tests and the full suite pass.

#### [ ] Step 8: Manual smoke test in Telegram
- **Files:** No source edits expected.
- **Action:** Create a small expense through the bot, run `/recent`, then run `/editar monto <nuevo_monto>` and `/editar categoria <categoria>`. Verify YNAB reflects the requested changes and the bot returns the Spanish success message.
- **Tests:** Manual verification recorded in implementation notes.

## Constraints & Architecture
- YNAB is the financial source of truth; never trust local recent cache over live YNAB.
- `/recent`, `/editar`, and `/deshacer` remain workflow conveniences, not canonical reporting.
- Use `YNABRepositoryFactory` per user; do not introduce singleton YNAB clients.
- Preserve milliunit rules: YNAB amounts are multiplied by 1000 and expenses are negative.
- No migration is expected. If implementation needs new persisted reconciliation metadata, consult the Database Advisor role before coding.
- All Python commands must use `.venv/bin/pytest`.

## Verification
- [x] Targeted service tests pass.
- [x] Telegram learning handler tests pass.
- [x] Full `.venv/bin/pytest` suite passes.
- [x] Manual `/editar` smoke test succeeds against a fresh bot-created transaction.
- [x] Missing/deleted YNAB transaction cases remain blocked for `/editar`; drift remains blocked for `/deshacer`.
