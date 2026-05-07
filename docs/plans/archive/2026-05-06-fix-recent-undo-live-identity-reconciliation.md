# Plan: Fix Recent Undo Live Identity Reconciliation

## Objective & Context
- **Status:** Completed
- **Source Spec:** `docs/specs/archive/2026-05-06-fix-recent-undo-live-identity-reconciliation.md`
- **Harness Roadmap Marker:** E.10
- **Goal:** Make `/deshacer` target an existing live YNAB transaction by ID instead of rejecting benign local cache drift.
- **Approach:** Add focused regressions, route undo through live-identity reconciliation, update behavioral invariant references, and document the revised durable policy.

## Affected Components
- `src/application/services/expense_service.py` — undo live transaction reconciliation.
- `tests/application/services/test_expense_service.py` — service regressions for undo drift and missing live transactions.
- `scripts/harness/behavioral_invariants.py` and harness tests — expected invariant wording for undo.
- `docs/adrs/2026-05-06-recent-undo-live-ynab-reconciliation.md` — policy ADR.
- `docs/adrs/2026-04-25-recent-edit-live-ynab-reconciliation.md` — mark the older undo-strict consequence as superseded.

## Prerequisites (Manual)
- [x] Read `docs/AI_WORKFLOW.md`, `docs/DOCUMENTATION_WORKFLOW.md`, `docs/wip_state.md`, and role contracts.
- [x] Trace current `/editar` and `/deshacer` implementation before changing code.

## Implementation Steps

### Group 1
<!-- Capture the failing behavior first. -->

#### [x] Step 1: Add undo drift regression tests
- **Role:** Test Writer
- **Files:** `tests/application/services/test_expense_service.py`
- **Write Scope:** `tests/application/services/test_expense_service.py`
- **Read Scope:** `src/application/services/expense_service.py`, `docs/specs/archive/2026-05-06-fix-recent-undo-live-identity-reconciliation.md`
- **Depends On:** None
- **Auto-Delegable:** no
- **Escalation Target:** Debugger
- **Action:** Add tests showing `/deshacer` succeeds when the live YNAB transaction exists despite cached amount/payee/category drift, and still fails when the live transaction is missing.
- **Verification:** `.venv/bin/pytest tests/application/services/test_expense_service.py -q`

### Group 2 (depends on: Group 1)
<!-- Implement the service behavior. -->

#### [x] Step 2: Route undo through live identity reconciliation
- **Role:** Step Implementer
- **Files:** `src/application/services/expense_service.py`
- **Write Scope:** `src/application/services/expense_service.py`
- **Read Scope:** `tests/application/services/test_expense_service.py`, `docs/specs/archive/2026-05-06-fix-recent-undo-live-identity-reconciliation.md`
- **Depends On:** Group 1
- **Auto-Delegable:** no
- **Escalation Target:** Debugger
- **Action:** Make `undo_last_transaction` require live transaction existence by ID, without strict cached metadata comparisons, while preserving existing failure codes and delete-side effects.
- **Verification:** `.venv/bin/pytest tests/application/services/test_expense_service.py -q`

### Group 3 (depends on: Group 2)
<!-- Keep executable documentation aligned. -->

#### [x] Step 3: Update behavioral invariant docs and tests
- **Role:** Step Implementer
- **Files:** `scripts/harness/behavioral_invariants.py`, `tests/harness/test_checks.py`
- **Write Scope:** `scripts/harness/behavioral_invariants.py`, `tests/harness/test_checks.py`
- **Read Scope:** `src/application/services/expense_service.py`, `docs/adrs/2026-04-25-recent-edit-live-ynab-reconciliation.md`
- **Depends On:** Group 2
- **Auto-Delegable:** no
- **Escalation Target:** Debugger
- **Action:** Replace the old invariant that undo blocks benign stale metadata with the new invariant that undo trusts an existing live YNAB ID but still blocks missing live transactions.
- **Verification:** `.venv/bin/pytest tests/harness/test_checks.py -q`

### Group 4 (depends on: Group 3)
<!-- Document the revised decision and close out. -->

#### [x] Step 4: Document and verify
- **Role:** Orchestrator
- **Files:** `docs/adrs/2026-05-06-recent-undo-live-ynab-reconciliation.md`, `docs/adrs/2026-04-25-recent-edit-live-ynab-reconciliation.md`, `docs/wip_state.md`
- **Write Scope:** docs only
- **Read Scope:** `docs/specs/archive/2026-05-06-fix-recent-undo-live-identity-reconciliation.md`, `docs/plans/archive/2026-05-06-fix-recent-undo-live-identity-reconciliation.md`
- **Depends On:** Group 3
- **Auto-Delegable:** no
- **Escalation Target:** User
- **Action:** Add ADR, update older ADR supersession metadata, run targeted and relevant harness verification, then update WIP state.
- **Verification:** `.venv/bin/pytest tests/application/services/test_expense_service.py tests/presentation/telegram/test_learning_handler.py tests/harness/test_checks.py -q`

## Constraints & Architecture
- Preserve YNAB source-of-truth behavior.
- Preserve dependency injection through `YNABRepositoryFactory`.
- Preserve per-user repository and learning calls.
- Keep Telegram-facing text in Spanish.
- No database migration.

## Verification
- [x] `.venv/bin/pytest tests/application/services/test_expense_service.py -q`
- [x] `.venv/bin/pytest tests/application/services/test_expense_service.py tests/presentation/telegram/test_learning_handler.py tests/harness/test_checks.py -q`
