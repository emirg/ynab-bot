# Spec: Compact Monthly /resumen

## Metadata
- **Status:** Implemented
- **Owner:** Codex
- **Related Roadmap Item:** 3.5 — Resumen On-Demand
- **Related ADRs:** None

## Summary
The monthly `/resumen` response should become shorter, more actionable, and easier to scan in Telegram. Instead of listing every category and every budget line in the first message, the bot should present a compact monthly health summary that highlights overspending, near-limit categories, and the most relevant next action. Users can still access deeper monthly detail through inline buttons.

## Problem
- The current `/resumen mes` output is too long because it combines total spent, the full category ranking, and the full budget comparison in a single message.
- The most important signals are buried inside raw detail, which makes the summary less useful as a quick monthly check-in.

## Goals
- Make `/resumen mes` readable in one screen for typical monthly usage.
- Prioritize budget-health insights over exhaustive detail.
- Preserve access to deeper monthly detail without forcing users to read it by default.

## Non-Goals
- Redesign `/resumen dia` or `/resumen semana` in this change.
- Add forecasting, historical month-over-month comparisons, or advisor-style LLM analysis.
- Change YNAB data sources, persistence, or authentication behavior.

## Users / Consumers
- Telegram users who check monthly spending health with `/resumen` or `/resumen mes`.
- Future maintainers of the summary service, formatter, and Telegram interaction flow.

## Expected Behavior
- `/resumen` and `/resumen mes` still target the current calendar month by default.
- The first monthly message shows:
  - month label
  - total spent
  - a short monthly status block
  - a capped set of high-signal findings only
  - an inline keyboard for drill-down
- High-signal findings are limited to budget-health items:
  - overspent categories
  - categories using at least 90% of budget but not yet overspent
  - optionally the top spending category or strongest remaining safe margin when no risk signals dominate
- The first message must not dump every category or every budget comparison line.
- Inline buttons open scoped monthly detail views:
  - `Ver categorías`
  - `Ver presupuesto`
  - `Volver al resumen`
- Detail views should edit the existing Telegram message instead of sending a new long thread when possible.
- Empty-state behavior remains friendly and short when there are no expenses in the month.

## Inputs and Outputs
- **Inputs:** `/resumen`, `/resumen mes`, monthly YNAB transactions, monthly YNAB category budget/activity data, Telegram callback actions
- **Outputs:** compact monthly Telegram message, drill-down detail messages via callback-driven message edits
- **Public Interfaces:** `/resumen`, `/resumen mes`, callback data for monthly summary drill-down

## Business Rules and Constraints
- All user-facing strings remain in Spanish.
- All amounts continue to use milliunit-safe handling.
- Expenses remain derived from negative YNAB activity/transaction amounts and displayed as positive values.
- Per-user isolation remains unchanged; all YNAB access must stay scoped through `YNABRepositoryFactory`.
- “En riesgo” means budget usage is at least 90% and the category is not yet overspent.
- Overspent categories have higher priority than “en riesgo” categories in the compact summary.
- The compact summary should cap visible insight items to avoid recreating the current overload.
- Inline callback data must stay within Telegram limits and follow existing bot callback patterns.

## Edge Cases and Failure Handling
- If there are no expenses in the month, return the existing short empty-state message and omit drill-down buttons.
- If there is budget data but no overspent or at-risk category, the summary should still provide a useful status and at least one positive or neutral signal.
- If budget comparison data is unavailable for any reason while monthly transactions exist, the summary should degrade gracefully to spending-focused output rather than fail.
- If a callback references a monthly detail view but there is no detail to show, return a short explanatory message and keep the interaction stable.
- Invalid or stale callbacks should fail safely with a short Telegram response, consistent with existing callback handlers.

## Acceptance Criteria
- [ ] `/resumen mes` returns a compact monthly summary instead of the current exhaustive listing.
- [ ] The compact monthly summary prioritizes overspent and near-limit categories before general detail.
- [ ] Categories at or above 90% of budget usage are flagged as “en riesgo” when not overspent.
- [ ] Users can open monthly detail views from inline buttons without rerunning the command.
- [ ] `/resumen dia` and `/resumen semana` behavior is unchanged in this slice.
- [ ] Empty-state, YNAB API failure, and auth failure behavior remain correct.

## Open Questions
- None.

## References
- `docs/plans/archive/milestone-3.5-resumen-on-demand.md`
- `src/application/services/on_demand_summary_service.py`
- `src/presentation/telegram/formatters.py`
- `src/presentation/telegram/handlers/summary_handler.py`
