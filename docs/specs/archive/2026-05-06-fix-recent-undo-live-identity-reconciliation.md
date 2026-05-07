# Spec: Fix Recent Undo Live Identity Reconciliation

## Metadata
- **Status:** Implemented
- **Owner:** Codex
- **Related Roadmap Item:** Maintenance: recent transaction reconciliation
- **Related ADRs:** `docs/adrs/2026-04-25-recent-edit-live-ynab-reconciliation.md`, `docs/adrs/2026-05-06-recent-undo-live-ynab-reconciliation.md`
- **Harness Roadmap Marker:** E.10

## Summary
`/deshacer` can reject a recent transaction as stale even when the transaction still exists in YNAB and was not edited by the user. The undo flow should target the live YNAB transaction by ID, matching the source-of-truth policy already used by `/editar`, while preserving safe failures for missing IDs, missing live transactions, and expired undo windows.

## Problem
- The local recent transaction cache is populated from the bot's `Expense` object before YNAB returns the canonical transaction payload.
- YNAB can canonicalize payee names, category fields, split structure, or amounts on creation, so strict local-vs-live metadata comparisons can fail immediately after a bot-created transaction.
- The delete operation still targets a concrete `ynab_transaction_id`, so blocking on cache metadata drift prevents legitimate undo operations.

## Goals
- Let `/deshacer` delete the referenced live YNAB transaction when the cached row has a valid `ynab_transaction_id` and YNAB still returns that transaction.
- Keep `/editar` live-identity behavior unchanged.
- Preserve existing safe failures for no recent row, no YNAB transaction ID, missing/deleted live YNAB transaction, YNAB delete failure, and time-window expiry.
- Add regression tests for benign live/cache drift on undo.

## Non-Goals
- Do not turn `/recent` into a live YNAB browser.
- Do not add database columns or migrations.
- Do not change Telegram command syntax.

## Users / Consumers
- Telegram users who create a transaction through the bot and then immediately use `/deshacer` or `/editar`.
- Maintainers extending recent/edit/undo reconciliation behavior.

## Expected Behavior
- `/deshacer` should use the cached `ynab_transaction_id` to fetch the live transaction.
- If YNAB returns the transaction, `/deshacer` should attempt deletion even if cached payee, amount, category, or split metadata differs from the live payload.
- If YNAB does not return the transaction, `/deshacer` should still fail with the existing sync error.
- `/editar` should continue to trust live YNAB identity when the transaction exists.

## Inputs and Outputs
- **Inputs:** `/deshacer`, `/editar ...`, recent transaction cache rows, YNAB transaction fetch/delete/update responses
- **Outputs:** Spanish Telegram success or error messages, YNAB delete/update side effects, learning/recent cache updates
- **Public Interfaces:** Telegram `/deshacer`, `/editar`, `/recent`

## Business Rules and Constraints
- YNAB is the financial source of truth.
- Recent/edit/undo state is a workflow convenience, not authoritative reporting.
- YNAB amounts are milliunits; user-facing cached amounts remain major units.
- User-facing Telegram text stays Spanish.
- Per-user isolation is preserved through `telegram_user_id` and per-user YNAB repositories.

## Edge Cases and Failure Handling
- No local recent transaction returns the current no-recent error.
- Missing `ynab_transaction_id` returns the current no-ID error.
- Missing or deleted live YNAB transaction returns the current sync error.
- Expired edit/undo window returns the current time-window error.
- YNAB delete failure returns the current delete-failed error without mutating learning or recent cache.

## Acceptance Criteria
- [x] `/deshacer` succeeds when live YNAB payee differs only because of canonicalization.
- [x] `/deshacer` succeeds when live YNAB amount/category metadata differs but the transaction ID exists.
- [x] `/deshacer` still blocks when YNAB no longer returns the transaction.
- [x] `/editar` regression tests continue to pass.
- [x] Behavioral invariant docs/tests no longer claim undo must block benign metadata drift.

## Open Questions
- None.

## References
- `docs/adrs/2026-04-12-ynab-source-of-truth.md`
- `docs/adrs/2026-04-25-recent-edit-live-ynab-reconciliation.md`
- `src/application/services/expense_service.py`
- `tests/application/services/test_expense_service.py`
