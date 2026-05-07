# ADR: Recent Undo Uses Live YNAB Transaction Identity

## Metadata
- **Status:** Accepted
- **Date:** 2026-05-06
- **Related Spec:** `docs/specs/archive/2026-05-06-fix-recent-undo-live-identity-reconciliation.md`
- **Related Plan:** `docs/plans/archive/2026-05-06-fix-recent-undo-live-identity-reconciliation.md`
- **Supersedes:** Undo-specific strict stale-check consequence in `docs/adrs/2026-04-25-recent-edit-live-ynab-reconciliation.md`
- **Superseded By:** None

## Context

`/deshacer` deletes a specific YNAB transaction by `ynab_transaction_id`, but the previous implementation first compared the bot's cached recent row against the live YNAB transaction. That strict check could reject an untouched bot-created transaction when YNAB canonicalized payee names, category fields, amount shape, or split structure during creation.

This made the local recent cache more authoritative than YNAB even though the live transaction ID still existed and the delete call would target that exact transaction.

## Decision

`/deshacer` now uses the same live-identity reconciliation policy as `/editar`: if the local recent row has a `ynab_transaction_id` and YNAB returns that transaction, the command may proceed.

The implementation still fails safely when:

- the user has no recent local row
- the local row has no `ynab_transaction_id`
- YNAB no longer returns the transaction
- the edit/undo time window has expired
- the YNAB delete call fails

Benign drift in cached payee, amount, category, or split metadata no longer blocks deletion of the referenced live transaction.

## Alternatives Considered

- **Keep strict metadata equality for undo:** Rejected because it blocks legitimate undo operations after YNAB canonicalizes a bot-created transaction.
- **Allow undo without fetching live YNAB first:** Rejected because missing or deleted transactions should still produce the existing sync error before local learning/cache mutations.
- **Refresh `/recent` from live YNAB before every undo:** Rejected as larger than this bugfix and unnecessary for targeting a known transaction ID.

## Consequences

- **Positive:** Immediate `/deshacer` works for bot-created transactions even when the live YNAB payload differs from the cached creation payload.
- **Positive:** `/editar` and `/deshacer` now consistently treat live YNAB identity as authoritative for targeted mutations.
- **Negative:** If a user materially edits the same transaction directly in YNAB before using `/deshacer`, the bot may still delete it as long as the ID exists and the time window allows it.
- **Follow-up:** Consider making `/recent` refresh display metadata from live YNAB so users can see canonicalized fields before choosing edit or undo actions.

## References

- `docs/adrs/2026-04-12-ynab-source-of-truth.md`
- `docs/adrs/2026-04-25-recent-edit-live-ynab-reconciliation.md`
- `docs/specs/archive/2026-05-06-fix-recent-undo-live-identity-reconciliation.md`
- `docs/plans/archive/2026-05-06-fix-recent-undo-live-identity-reconciliation.md`
- `src/application/services/expense_service.py`
- `tests/application/services/test_expense_service.py`
