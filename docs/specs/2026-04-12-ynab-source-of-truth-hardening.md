# Spec: YNAB Source Of Truth Hardening

## Metadata
- **Status:** Draft
- **Owner:** Codex
- **Related Roadmap Item:** 3.5 — Resumen On-Demand, Advisor ongoing slices
- **Related ADRs:** `docs/adrs/2026-04-12-ynab-source-of-truth.md`

## Summary
The app must treat YNAB as the authoritative financial system for all app-wide financial behavior. Any user-facing financial value shown by the bot or advisor must come from the correct YNAB source for that kind of value, rather than from local inference when YNAB already provides the relevant state. This spec defines the source-of-truth matrix for spending totals, category rankings, budget status, account balances, workflow-local state, and failure behavior.

## Problem
- Different parts of the app currently use different definitions of "spent", "remaining", and "top categories".
- Some views use raw transactions, some use category activity, and some historically inferred remaining budget from `budgeted - spent` instead of YNAB `balance`.
- Users may add, edit, split, recategorize, or reconcile transactions directly in YNAB, so bot-local interpretations can drift from reality.
- There is no single implementation rule future developers or AI agents can follow to avoid reintroducing these inconsistencies.

## Goals
- Define a single authoritative rule for financial reads across the app.
- Make monthly totals and category rankings match YNAB Reflect-style spending semantics wherever feasible.
- Keep budget-health views aligned with YNAB category state.
- Preserve bot workflow conveniences without confusing them with authoritative financial reporting.
- Fail closed when a feature needs YNAB-authoritative data and that data is unavailable.

## Non-Goals
- Build a full local sync engine or offline mirror of YNAB.
- Redesign Telegram UX or advisor UI layout in this slice.
- Change OAuth, auth, or persistence architecture beyond what is required for source-of-truth correctness.
- Turn `/recent` into a full YNAB transaction browser in this slice.

## Users / Consumers
- Telegram users relying on `/resumen`, budget queries, `/recent`, `/editar`, and `/deshacer`
- Advisor users relying on dashboard metrics and insights
- Developers and AI agents extending any financial feature

## Expected Behavior
- All financial features use an explicit source-of-truth matrix:
  - Spending totals, category rankings, and trend series use YNAB transactions, expanded by split subtransactions, filtered to the app's Reflect-compatible spending definition.
  - Budget status, category available, overspending, assigned, and monthly activity use YNAB category snapshot fields: `budgeted`, `activity`, and `balance`.
  - Account balances use YNAB account balance fields.
  - Bot-local workflow state may exist for confirmation, learning, or recent-action convenience, but must not be treated as authoritative financial state.
- Monthly spending totals shown in `/resumen`, advisor dashboard, and any budget-summary-style output target the same YNAB Reflect-compatible definition.
- Day and week category breakdowns remain period-scoped from transactions, but expand split subtransactions and ignore zero-sum bookkeeping artifacts.
- Monthly budget warnings are based on YNAB `balance < 0`, not locally derived remaining formulas.
- `/recent`, `/editar`, and `/deshacer` remain workflow conveniences based on recent bot-tracked references, but documentation and copy make clear they are convenience actions, not full financial reporting.
- If a feature requires YNAB-authoritative data and that data cannot be fetched or validated, it fails with an explicit unavailable or error state instead of showing guessed financial numbers.

## Inputs and Outputs
- **Inputs:** Telegram commands, advisor dashboard requests, YNAB transactions, YNAB category/account snapshots, callback actions, locally tracked recent-action references
- **Outputs:** Telegram messages, advisor dashboard payloads, budget query responses, authoritative errors or unavailable states when YNAB cannot be used
- **Public Interfaces:** `/resumen`, weekly summary, advisor dashboard API, budget queries, `/recent`, `/editar`, `/deshacer`

## Business Rules and Constraints
- YNAB is the financial source of truth.
- If YNAB provides the relevant financial value directly, prefer YNAB over local derivation.
- Spending semantics and budget semantics are different and must not share one calculation path by default.
- "Reflect-compatible spending" means transaction-based monthly spending that expands split subtransactions, excludes non-spending artifacts such as transfers, and uses net category activity for totals.
- For monthly totals specifically, negative category activity increases spending, real categorized inflows can offset spending, but `Inflow: Ready to Assign` must not offset spending.
- Monthly category rankings should show categories whose net activity remains negative after the monthly netting step.
- Monthly category budget health uses category snapshots, not transaction aggregation.
- Local recent-transaction state is convenience metadata only.
- All user-facing strings remain in Spanish.
- All amounts remain milliunits internally.
- Per-user isolation and `YNABRepositoryFactory` usage remain mandatory.

## Edge Cases and Failure Handling
- Split parent transactions must not swallow real category amounts.
- Zero-sum split bookkeeping transactions must not inflate spending totals.
- Carryover-positive categories must not be marked overspent.
- If YNAB category data is unavailable, budget-health views fail closed rather than inventing a fallback.
- If YNAB transaction data is unavailable, spending-total views fail closed rather than using local approximations.
- If a local recent transaction points to a YNAB transaction that no longer exists or was changed materially, `/editar` and `/deshacer` fail safely with a clear user message.
- Hidden/deleted categories and closed/deleted accounts continue to be excluded from user-facing active summaries unless explicitly required.

## Acceptance Criteria
- [ ] A documented source-of-truth matrix exists and is referenced by architecture and workflow docs.
- [ ] `/resumen dia`, `/resumen semana`, and weekly summary category totals correctly expand split subtransactions.
- [ ] `/resumen mes`, advisor monthly totals, and any budget-summary-style spending total use the same Reflect-compatible spending definition.
- [ ] Budget-health logic across `/resumen` and advisor uses YNAB category `balance` for overspending and remaining available.
- [ ] Category/account balance queries remain directly YNAB-backed.
- [ ] `/recent`, `/editar`, and `/deshacer` are documented as workflow conveniences, not canonical reporting.
- [ ] When authoritative YNAB data cannot be fetched, affected financial reads fail closed instead of showing guessed totals.

## Open Questions
- None. Chosen defaults:
  - Scope: app-wide financial behavior
  - Spending total target: mirror YNAB Reflect-style spending semantics
  - Failure mode: fail closed
  - Recent/edit/undo policy: keep as workflow conveniences

## References
- `README.md`
- `docs/AI_WORKFLOW.md`
- `docs/ARCHITECTURE.md`
- `AGENTS.md`
- `docs/adrs/2026-04-12-ynab-source-of-truth.md`
- `src/application/services/on_demand_summary_service.py`
- `src/application/services/advisor_dashboard_service.py`
- `src/application/services/budget_query_service.py`
- `src/domain/models/weekly_summary.py`
- `src/domain/models/on_demand_summary.py`
