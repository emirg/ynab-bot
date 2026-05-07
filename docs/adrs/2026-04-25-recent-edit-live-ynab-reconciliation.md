# ADR: Recent Edit Uses Live YNAB Transaction Identity

## Metadata
- **Status:** Accepted
- **Date:** 2026-04-25
- **Related Spec:** `docs/specs/archive/2026-04-25-fix-recent-transaction-edit-reconciliation.md`
- **Related Plan:** `docs/plans/archive/2026-04-25-fix-recent-transaction-edit-reconciliation.md`
- **Supersedes:** None
- **Superseded By:** Undo-specific strict stale-check consequence superseded by `docs/adrs/2026-05-06-recent-undo-live-ynab-reconciliation.md`

## Context

`/recent`, `/editar`, and `/deshacer` use locally cached recent transaction references as workflow conveniences. That cache can drift because users may edit payees, amounts, categories, split structure, or reconciliation state directly in YNAB.

The previous edit flow treated drift between the cached recent row and the live YNAB transaction as a stale-reference error. In practice this blocked legitimate `/editar` requests even when the cached row still had the correct `ynab_transaction_id` and YNAB still returned the live transaction.

This created tension with the project rule that YNAB is the financial source of truth: local cached metadata was preventing updates to an existing authoritative YNAB transaction.

## Decision

`/editar` targets a concrete YNAB transaction ID. If that ID exists in live YNAB, the edit flow treats the live YNAB transaction as authoritative and applies only the requested field changes.

The implementation:

- still fails safely when the local row has no `ynab_transaction_id`
- still fails safely when YNAB no longer returns that transaction
- no longer blocks `/editar` because cached payee, amount, or category differ from live YNAB
- logs cache drift for diagnosis
- refreshes the local recent cache from live YNAB after a successful edit where relevant
- originally kept `/deshacer` on the stricter stale-check path because deleting an entire transaction has higher risk than editing requested fields; this undo-specific consequence is superseded by `docs/adrs/2026-05-06-recent-undo-live-ynab-reconciliation.md`

## Alternatives Considered

- **Keep strict equality for `/editar`:** Rejected because local recent metadata can drift from YNAB and should not override the live YNAB transaction when the ID still exists.
- **Remove all recent-reference validation:** Rejected because missing IDs and deleted/inaccessible YNAB transactions must still fail safely.
- **Make `/recent` a full live YNAB browser now:** Rejected as larger than this bugfix. It remains a possible future improvement.

## Consequences

- **Positive:** Legitimate `/editar` requests work even after harmless or user-driven YNAB changes.
- **Positive:** The flow better follows the YNAB source-of-truth rule.
- **Superseded:** `/deshacer` no longer blocks benign local metadata drift when YNAB still returns the referenced live transaction ID.
- **Negative:** A user can edit a live YNAB transaction whose cached display metadata no longer matches what `/recent` showed. The target is still the same transaction ID, but the UI may feel stale until `/recent` is refreshed.
- **Follow-up:** Consider a later `/recent` improvement that refreshes displayed rows from live YNAB before showing edit indices.

## References

- `docs/adrs/2026-04-12-ynab-source-of-truth.md`
- `docs/specs/archive/2026-04-25-fix-recent-transaction-edit-reconciliation.md`
- `docs/plans/archive/2026-04-25-fix-recent-transaction-edit-reconciliation.md`
- `src/application/services/expense_service.py`
- `tests/application/services/test_expense_service.py`
