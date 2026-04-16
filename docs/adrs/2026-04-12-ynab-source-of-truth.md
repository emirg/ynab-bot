# ADR: YNAB As Financial Source Of Truth

## Metadata
- **Status:** Accepted
- **Date:** 2026-04-12
- **Related Spec:** `docs/specs/2026-04-12-resumen-mensual-compacto.md`
- **Related Plan:** `docs/plans/2026-04-12-resumen-mensual-compacto.md`
- **Supersedes:** None
- **Superseded By:** None

## Context

The product lets users register expenses through the bot, but that is not the only way financial data changes. Users can also:

- add transactions directly in YNAB
- edit or recategorize existing transactions in YNAB
- create split transactions in YNAB
- move money between categories in YNAB
- rely on YNAB category activity and available balances that include carryover behavior

This creates a recurring risk: local application logic may compute a financial view that diverges from what YNAB actually shows. Recent issues in monthly summaries and advisor views exposed that risk when transaction-only aggregation disagreed with YNAB category activity or when locally derived remaining budget disagreed with YNAB available balance.

Because users trust YNAB as their budgeting system of record, the app must not present an alternative financial reality.

## Decision

YNAB is the financial source of truth for this project.

The implementation must follow these rules:

- When YNAB exposes the relevant financial state directly, prefer YNAB data over locally inferred or cached interpretations.
- Monthly budget-health and availability decisions should prefer YNAB category activity/balance when monthly category snapshots are available.
- Monthly spending totals still come from transactions, but they must follow Reflect-style net category activity semantics rather than a raw "sum all negative rows" rule.
- Under that rule, real categorized inflows may offset monthly spending, while bookkeeping flows such as transfers and `Inflow: Ready to Assign` must not reduce spending.
- Budget remaining or overspending decisions should prefer YNAB category balance/available amount when available.
- Period-scoped views that must still rely on transactions, such as day or week category breakdowns, must interpret YNAB transaction structure faithfully, including split subtransactions.
- Local persistence, summaries, and advisor logic are supporting views and workflows, not an independent ledger.

This rule applies to product behavior, engineering changes, and AI-assisted implementation work.

## Alternatives Considered

- **Local app state as the primary ledger:** Rejected because it will drift whenever users edit data directly in YNAB.
- **Transaction-only derivation for every view:** Rejected because it can misrepresent split transactions and miss YNAB category semantics such as carryover and available balance.
- **Hybrid undocumented approach:** Rejected because inconsistent assumptions across features are hard to detect and easy for future contributors or AI agents to break.

## Consequences

- **Positive:** User-facing numbers are more trustworthy and match the budgeting tool users already rely on.
- **Positive:** Developers and AI assistants have a clear rule for resolving ambiguity in calculations and data modeling.
- **Positive:** Bugs caused by local over-interpretation become easier to classify and fix.
- **Negative:** Some views must fetch and reconcile richer YNAB data instead of relying on simpler local aggregation.
- **Negative:** Engineering work must distinguish carefully between month-scoped YNAB category state and narrower transaction-scoped periods like day and week.
- **Follow-up:** Keep this rule visible in user-facing and developer-facing documentation, and review new reporting features against it during spec and code review.

## References

- `README.md`
- `docs/AI_WORKFLOW.md`
- `docs/ARCHITECTURE.md`
- `AGENTS.md`
- `docs/dev/README.md`
- `src/application/services/on_demand_summary_service.py`
- `src/application/services/advisor_dashboard_service.py`
