# Spec: Fix Recent Transaction Edit Reconciliation

## Metadata
- **Status:** Implemented
- **Owner:** Codex
- **Related Roadmap Item:** Bugfix: high-priority `/editar` regression
- **Related ADRs:** `docs/adrs/2026-04-12-ynab-source-of-truth.md`, `docs/adrs/2026-04-25-recent-edit-live-ynab-reconciliation.md`

## Summary
The `/editar` command currently fails for legitimate recent transactions with the message that the recent reference no longer matches YNAB. The bot must keep YNAB as the financial source of truth while avoiding false stale detections caused by harmless formatting, payee normalization, split transaction shape, account transfer fields, or local cache drift. Editing should reconcile against the live YNAB transaction and update only the requested fields.

## Problem
- Users cannot edit recent transactions because the service returns `ynab_transaction_stale` too broadly.
- The stale-reference error is useful when YNAB really changed, but it should not block edits when the live transaction still corresponds to the cached recent reference.
- `/recent`, `/editar`, and `/deshacer` are convenience flows, so they must fail safely when the target truly disappeared or became ambiguous, but they should not require exact equality for display-only cached fields.

## Goals
- Restore `/editar monto|comercio|categoria|cuenta` for valid recent transactions.
- Continue blocking edits when the referenced YNAB transaction is missing, while reconciling benign cache drift from live YNAB state.
- Reconcile against live YNAB fields with tolerant, explicit comparison rules.
- Keep the success/error messaging in Spanish and aligned with existing formatter patterns.

## Non-Goals
- Turning `/recent` into a full YNAB transaction browser.
- Allowing edits to arbitrary historical YNAB transactions.
- Changing `/deshacer` semantics unless shared reconciliation helpers require targeted adjustment.
- Adding a new database table or changing the YNAB source-of-truth policy.

## Users / Consumers
- Telegram users using `/editar` immediately after creating a bot-tracked expense.
- Maintainers relying on the local recent transaction cache for workflow convenience.
- The learning system that records category corrections after edits.

## Expected Behavior
- `/editar monto 30000` updates the most recent matching YNAB transaction amount when the YNAB transaction still corresponds to the cached recent item.
- `/editar 2 categoria Restaurantes` targets the second recent reference and updates the live YNAB transaction after tolerant reconciliation.
- If YNAB changed only display formatting, payee punctuation, category representation through subtransactions, or other benign fields, edit proceeds.
- If YNAB transaction ID is missing, deleted, or inaccessible, edit fails safely.
- If the YNAB transaction exists but its payee, amount, or category changed outside the bot, `/editar` uses the live YNAB transaction as authoritative and applies only the requested edits.
- After a successful edit, the local recent cache is updated with the edited fields so later `/recent`, `/editar`, and `/deshacer` use the newest convenience reference.

## Inputs and Outputs
- **Inputs:** `/editar` command arguments, local recent transaction rows, live YNAB transaction payloads, YNAB categories/accounts
- **Outputs:** YNAB transaction update requests, local recent transaction cache updates, Spanish Telegram responses
- **Public Interfaces:** `/editar`, `/recent`, `/deshacer` behavior where reconciliation helpers are shared

## Business Rules and Constraints
- YNAB remains authoritative for live transaction state.
- Local recent transactions are convenience references, not canonical financial records.
- Expenses sent to YNAB use negative milliunits.
- YNAB repository access must remain per-user via `YNABRepositoryFactory`.
- SQLite/Postgres recent cache queries must remain scoped by Telegram user ID.
- User-facing messages must remain Spanish.

## Edge Cases and Failure Handling
- No recent transactions: return the existing no-recent or out-of-range error consistently.
- Missing `ynab_transaction_id`: fail safely with the existing error path.
- Live transaction missing/deleted: return `ynab_transaction_missing`.
- Live transaction has subtransactions: compare against matching subtransactions when the parent category is empty.
- Live payee differs only by punctuation, casing, accents, or YNAB canonicalization: treat as matching.
- Amount representation differs only by local display units versus YNAB milliunits: treat as matching.
- Account edit requested and account lookup fails: keep existing account-not-found behavior.
- Category edit requested and category lookup fails: keep existing category-not-found behavior.

## Acceptance Criteria
- [x] Existing `/editar` unit tests pass.
- [x] New tests cover benign live/cache drift that should not return `ynab_transaction_stale`.
- [x] Missing/deleted live transactions still block edits.
- [x] Handler tests verify stale/missing errors still use the Spanish sync error formatter.
- [x] Successful edits update YNAB first, then update the local recent cache.
- [x] No database migration is required.

## Open Questions
- Which exact production field differs when `/editar` currently always returns the sync error: amount, payee, category, subtransaction shape, account, or date?
- Resolved: `/editar` is less strict than `/deshacer`. It requires the YNAB transaction ID to still exist, then reconciles from live YNAB state because the requested edit targets that concrete YNAB transaction.
- Should `/recent` refresh entries from live YNAB before displaying edit indices in a later slice?

## References
- `src/application/services/expense_service.py`
- `src/presentation/telegram/handlers/learning_handler.py`
- `src/presentation/telegram/formatters.py`
- `tests/application/services/test_expense_service.py`
- `tests/presentation/telegram/test_learning_handler.py`
- `docs/adrs/2026-04-12-ynab-source-of-truth.md`
