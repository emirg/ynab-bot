# Spec: Compact Monthly /resumen

## Metadata
- **Status:** Implemented
- **Harness Roadmap Marker:** E.17
- **Owner:** Codex
- **Related Roadmap Item:** 3.5 — Resumen On-Demand
- **Related ADRs:** None recorded during implementation

## Summary
The monthly `/resumen` response should become shorter, more actionable, and easier to scan in Telegram. Instead of listing every category and every budget line in the first message, the bot should present a compact monthly health summary that highlights overspending, top categories, and the most relevant next action. Users can still access deeper monthly detail through inline buttons.

This slice also establishes a broader source-of-truth rule for spending views across the bot and advisor: category totals should come from YNAB-native data whenever the period semantics allow it, and split transactions must be expanded so category breakdowns do not silently undercount spending.

## Problem
- The current `/resumen mes` output is too long because it combines total spent, the full category ranking, and the full budget comparison in a single message.
- The most important signals are buried inside raw detail, which makes the summary less useful as a quick monthly check-in.

## Goals
- Make `/resumen mes` readable in one screen for typical monthly usage.
- Prioritize budget-health insights over exhaustive detail.
- Preserve access to deeper monthly detail without forcing users to read it by default.
- Keep category totals trustworthy across bot and advisor views, even when the user enters or edits transactions directly in YNAB.

## Non-Goals
- Redesign the visual layout of `/resumen dia`, `/resumen semana`, or the advisor dashboard in this change.
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
  - optionally the top spending category or a neutral positive signal when nothing is overspent
- The first message must not dump every category or every budget comparison line.
- Inline buttons open scoped monthly detail views:
  - `Ver categorías`
  - `Ver presupuesto`
  - `Volver al resumen`
- Detail views should edit the existing Telegram message instead of sending a new long thread when possible.
- Monthly category totals shown in `Ver categorías` should align with YNAB category activity for the month, even when spending came from split transactions.
- Day and week category breakdowns should stay period-scoped, but they must expand split subtransactions so category totals reflect the real categories inside each split.
- Advisor monthly totals, top categories, and budget status should align with YNAB category data for the month instead of being derived only from top-level transactions.
- Empty-state behavior remains friendly and short when there are no expenses in the month.

## Inputs and Outputs
- **Inputs:** `/resumen`, weekly summary job, advisor dashboard requests, YNAB transactions, YNAB category budget/activity/balance data, Telegram callback actions
- **Outputs:** compact monthly Telegram message, drill-down detail messages via callback-driven message edits, weekly summary payloads, advisor dashboard payloads
- **Public Interfaces:** `/resumen`, `/resumen mes`, weekly summary generation, advisor dashboard JSON, callback data for monthly summary drill-down

## Business Rules and Constraints
- All user-facing strings remain in Spanish.
- All amounts continue to use milliunit-safe handling.
- Expenses remain derived from negative YNAB activity/transaction amounts and displayed as positive values.
- Per-user isolation remains unchanged; all YNAB access must stay scoped through `YNABRepositoryFactory`.
- Monthly warnings should only be shown when YNAB available is actually negative.
- For monthly category totals, YNAB category `activity` is the source of truth when category snapshots are available.
- For day/week category totals, raw transactions remain the time-scoped source, but split subtransactions must be expanded and grouped by their real category names.
- When monthly budget status is shown, YNAB category `balance` is the source of truth for remaining available money.
- The compact summary should cap visible insight items to avoid recreating the current overload.
- Inline callback data must stay within Telegram limits and follow existing bot callback patterns.

## Edge Cases and Failure Handling
- If there are no expenses in the month, return the existing short empty-state message and omit drill-down buttons.
- If there is budget data but no overspent category, the summary should still provide a useful status and at least one positive or neutral signal.
- If budget comparison data is unavailable for any reason while monthly transactions exist, the summary should degrade gracefully to spending-focused output rather than fail.
- If a callback references a monthly detail view but there is no detail to show, return a short explanatory message and keep the interaction stable.
- Invalid or stale callbacks should fail safely with a short Telegram response, consistent with existing callback handlers.

## Acceptance Criteria
- [ ] `/resumen mes` returns a compact monthly summary instead of the current exhaustive listing.
- [ ] The compact monthly summary prioritizes overspent categories before general detail.
- [ ] Categories with positive YNAB available are not warned as risky in the Telegram summary.
- [ ] Monthly category totals and top-category rankings match YNAB category activity for the same month.
- [ ] Day and week category breakdowns count split transaction subcategories correctly.
- [ ] Advisor monthly totals, top categories, and overspending state align with YNAB category activity and balance.
- [ ] Users can open monthly detail views from inline buttons without rerunning the command.
- [ ] `/resumen dia` and `/resumen semana` behavior is unchanged in this slice.
- [ ] Empty-state, YNAB API failure, and auth failure behavior remain correct.

## Open Questions
- None.

## References
- `docs/plans/archive/milestone-3.5-resumen-on-demand.md`
- `src/application/services/on_demand_summary_service.py`
- `src/application/services/advisor_dashboard_service.py`
- `src/application/services/weekly_summary_service.py`
- `src/presentation/telegram/formatters.py`
- `src/presentation/telegram/handlers/summary_handler.py`
