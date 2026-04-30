# Plan: Compact Monthly /resumen

## Objective & Context
- **Status:** Completed
- **Harness Roadmap Marker:** E.17
- **Source Spec:** `docs/specs/archive/2026-04-12-resumen-mensual-compacto.md`
- **Goal:** Deliver a compact, budget-health-first monthly `/resumen` experience with inline drill-down views for monthly details.
- **Approach:** Keep the existing `/resumen` command and YNAB data flow, but add monthly insight derivation, a compact formatter path, callback-driven Telegram drill-down views, and a shared source-of-truth aggregation rule across `/resumen`, weekly summaries, and advisor dashboard views.

## Affected Components
- `src/domain/models/on_demand_summary.py` — extend monthly summary data with derived insight groups and keep monthly totals aligned with YNAB category activity
- `src/domain/models/weekly_summary.py` — keep day/week category breakdowns split-aware while preserving period-scoped totals
- `src/application/services/on_demand_summary_service.py` — derive monthly insight signals from existing transaction and category data
- `src/application/services/advisor_dashboard_service.py` — align monthly advisor totals, top categories, and budget status with YNAB category activity/balance
- `src/presentation/telegram/formatters.py` — add compact monthly formatter and detail-view formatters
- `src/presentation/telegram/keyboards.py` — add monthly summary drill-down keyboard
- `src/presentation/telegram/handlers/summary_handler.py` — send reply markup and handle monthly summary callbacks
- `src/presentation/telegram/bot.py` — register summary callback handler
- `src/domain/services/...` or equivalent shared helper — flatten split transactions for period-scoped category views
- `tests/test_weekly_summary_model.py`
- `tests/test_advisor_dashboard_service.py`
- `tests/test_on_demand_summary_model.py`
- `tests/test_on_demand_summary_service.py`
- `tests/test_on_demand_summary_formatter.py`
- `tests/test_summary_handler.py`

## Prerequisites (Manual)
- None.

## Implementation Steps

### Group 1

#### [x] Step 1: Define monthly insight shape
- **Files:** `src/domain/models/on_demand_summary.py`
- **Action:** Extend the monthly summary model so the formatter receives precomputed groups instead of inferring business meaning from raw lists. Include enough fields to render overspent categories, top categories, healthy aggregate signal, recommended action, and availability of drill-down views.
- **Tests:** `tests/test_on_demand_summary_model.py` — cover derived-field construction and milliunit-safe values.

#### [x] Step 2: Derive monthly insight signals in the service
- **Files:** `src/application/services/on_demand_summary_service.py`
- **Action:** Keep existing transaction/category fetch behavior, but for `period_type == "mes"` compute prioritized insight groups: overspent categories first, top categories by spend, healthy categories summarized as counts or best-safe-margin signal, and a short status classification plus recommended action. Cap the compact-summary inputs so the formatter never dumps everything by default.
- **Tests:** `tests/test_on_demand_summary_service.py` — verify overspent detection, prioritization order, graceful behavior without budget data, and unchanged day/week generation.

### Group 2 (depends on: Group 1)

#### [x] Step 3: Add compact monthly formatter paths
- **Files:** `src/presentation/telegram/formatters.py`
- **Action:** Keep existing day/week formatting intact. For month summaries, replace the current exhaustive output with header, total spent, short `Estado del mes`, capped insight bullets, and no full category dump in the default message. Add separate formatter methods for monthly compact summary, monthly category detail, and monthly budget detail. Ensure the budget detail view prioritizes actual overspending before healthy categories.
- **Tests:** `tests/test_on_demand_summary_formatter.py` — verify compact structure, capped insight items, positive or neutral fallback when nothing is wrong, and unchanged day/week rendering.

#### [x] Step 4: Add monthly drill-down keyboard
- **Files:** `src/presentation/telegram/keyboards.py`
- **Action:** Add an inline keyboard builder for monthly summary views with callback data for compact summary, categories detail, and budget detail. The callback tokens should follow the existing prefix-routing style and remain stable and short.
- **Tests:** `tests/test_summary_handler.py` or dedicated keyboard assertions — verify expected callback data and button labels.

### Group 3 (depends on: Group 2)

#### [x] Step 5: Wire monthly callbacks into the summary handler
- **Files:** `src/presentation/telegram/handlers/summary_handler.py`
- **Action:** Update `/resumen mes` handling to send the compact summary with reply markup. Add a callback handler that validates auth, answers the callback, rebuilds the monthly summary from current data, edits the message text for `resumen_mes_resumen`, `resumen_mes_categorias`, and `resumen_mes_presupuesto`, and preserves a `Volver al resumen` path. Keep existing invalid-period and YNAB/OAuth error handling intact.
- **Tests:** `tests/test_summary_handler.py` — cover `/resumen mes` with keyboard, callback routing, edit-message behavior, stale or invalid callback behavior, and no-regression handling for non-month periods.

#### [x] Step 6: Register the summary callback route
- **Files:** `src/presentation/telegram/bot.py`
- **Action:** Register a `CallbackQueryHandler` for the new monthly summary callback prefix without conflicting with config, split, admin, or expense callbacks.
- **Tests:** `tests/test_summary_handler.py` or bot registration tests — verify the callback path is reachable.

### Group 4 (depends on: Group 3)

#### [x] Step 7: Refresh command/help copy if needed
- **Files:** `src/presentation/telegram/formatters.py`, `README.md`
- **Action:** Update user-facing help text only if necessary to mention that monthly summaries now include drill-down buttons. Do not change the command syntax.
- **Tests:** Extend formatter/help tests only if copy changes are made.

### Group 5

#### [x] Step 8: Add split-aware transaction aggregation for day/week views
- **Files:** `src/domain/models/on_demand_summary.py`, `src/domain/models/weekly_summary.py`, shared aggregation helper module, related tests
- **Action:** Introduce a shared helper that expands negative split subtransactions into their real categories while ignoring parent split buckets for category ranking. Use it for day/week on-demand summaries and weekly summary generation so category totals remain period-scoped and split-aware.
- **Tests:** `tests/test_on_demand_summary_model.py`, `tests/test_weekly_summary_model.py` — verify split parent categories do not swallow real subcategory totals.

#### [x] Step 9: Align advisor monthly metrics with YNAB category snapshots
- **Files:** `src/application/services/advisor_dashboard_service.py`, `src/domain/models/advisor_dashboard.py`, `tests/test_advisor_dashboard_service.py`
- **Action:** For monthly advisor views, derive `total_spent`, `top_categories`, and budget status from YNAB category `activity`/`balance` instead of only top-level transactions. Keep day/week advisor views transaction-scoped but split-aware. Preserve trend calculations from dated transactions.
- **Tests:** `tests/test_advisor_dashboard_service.py` — verify monthly totals/top categories match category activity, carryover-positive categories are not marked overspent, and day/week split transactions group correctly.

## Constraints & Architecture
- Keep all user-facing strings in Spanish.
- Preserve milliunit invariants and existing YNAB transaction filtering behavior.
- Do not add DB schema changes, migrations, or persistent callback state.
- Rebuild monthly drill-down views from fresh service data rather than storing large state blobs in Telegram context.
- Keep `/resumen dia` and `/resumen semana` behavior unchanged in this implementation.
- Use existing Telegram callback conventions: short prefixes, handler pattern routing, and `edit_message_text` for drill-down navigation.

## Verification
- [x] `/resumen` and `/resumen mes` return the new compact monthly summary with inline buttons.
- [x] Overspent categories appear before all other signals in the first monthly screen.
- [x] Categories with positive YNAB available are not shown as risky in the Telegram summary.
- [x] Monthly category totals shown in `Ver categorías` align with YNAB category activity, including split-backed spending.
- [x] Day and week category breakdowns count split transaction subcategories correctly.
- [x] Advisor monthly totals, top categories, and overspending state align with YNAB category activity and balance.
- [x] `Ver categorías` shows monthly category detail without reopening the command.
- [x] `Ver presupuesto` shows budget exceptions first and allows returning to the summary.
- [x] `/resumen dia` still renders the current day summary as before.
- [x] `/resumen semana` still renders the current week summary as before.
- [x] YNAB API and OAuth failures remain user-friendly in Spanish.
