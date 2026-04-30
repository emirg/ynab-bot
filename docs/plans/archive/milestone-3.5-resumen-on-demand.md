# Plan: Milestone 3.5 — Resumen On-Demand (`/resumen`)

## Objective & Context
- **Status:** Completed
- **Harness Roadmap Marker:** 3.5
- **Goal:** Add a `/resumen` command that shows a spending summary for the current day, week, or month, with category breakdown and optional comparison against the YNAB budget.
- **Why:** Users want to check their spending at any time, not just via the automatic weekly summary. This gives them instant visibility into where their money is going and how it compares to their budget plan.

## Affected Components
- `src/domain/models/on_demand_summary.py` — **new** domain model for on-demand summaries
- `src/application/services/on_demand_summary_service.py` — **new** service for building summaries for any period
- `src/presentation/telegram/formatters.py` — add `OnDemandSummaryFormatter` class
- `src/presentation/telegram/handlers/summary_handler.py` — **new** handler for `/resumen`
- `src/presentation/telegram/bot.py` — register `/resumen` command and handler
- `src/infrastructure/container.py` — register `OnDemandSummaryService` in DI
- `tests/test_on_demand_summary_model.py` — **new** model tests
- `tests/test_on_demand_summary_service.py` — **new** service tests
- `tests/test_on_demand_summary_formatter.py` — **new** formatter tests
- `tests/test_summary_handler.py` — **new** handler tests

## Prerequisites (Manual)
- None. No new env vars, API keys, or infrastructure needed. The existing YNAB API endpoints (`get_transactions`, `get_categories`) provide all required data.

## Design Decisions

### Period selection
The command supports three periods via argument: `/resumen dia`, `/resumen semana`, `/resumen mes`. Default (no argument) is the current month, as it's the most useful overview. Aliases accepted:
- **dia/día/hoy/today** -> current day
- **semana/week** -> current ISO week (Monday-Sunday up to today)
- **mes/month** -> current calendar month (1st to today)

### Budget comparison
The YNAB categories API already returns `budgeted`, `activity`, and `balance` for the **current month**. For the monthly summary, we display budgeted vs. spent per category directly from the categories endpoint. For day/week summaries, we show category spending breakdown only (no budget comparison, since YNAB budgets are monthly). This is explicitly called out in the formatted message.

### Reuse of WeeklySummary patterns
The existing `WeeklySummary.from_transactions()` aggregates transactions by category and computes totals. The new `OnDemandSummary` model follows the same pattern (filter expenses, aggregate by category, sort descending) but adds: configurable period labels, budget comparison data (for monthly), and shows **all** categories instead of just top 3.

### No DB changes
This feature is purely read-only (YNAB API queries). No new tables, migrations, or persistence needed.

## Implementation Steps

### Group 1 — Domain model + Service (no file dependencies between them and the formatter)

#### [x] Step 1: Domain model — `OnDemandSummary`
- **Files:** `src/domain/models/on_demand_summary.py`
- **Action:** Create dataclass `OnDemandSummary` with fields:
  - `period_type: str` — "dia" | "semana" | "mes"
  - `period_label: str` — human-readable label, e.g. "Hoy (19/03)", "Semana (lun 17/03 - mié 19/03)", "Marzo 2026"
  - `total_spent: int` — milliunits, positive
  - `category_breakdown: List[CategorySpending]` — reuse `CategorySpending` from `weekly_summary.py`, sorted desc by amount
  - `budget_comparison: Optional[List[CategoryBudgetComparison]]` — only populated for monthly summaries
  - `has_transactions: bool`
  - `period_start: date`
  - `period_end: date`

  Create dataclass `CategoryBudgetComparison` with fields:
  - `category_name: str`
  - `budgeted: int` — milliunits, positive
  - `spent: int` — milliunits, positive (abs of activity)
  - `remaining: int` — milliunits (can be negative if overspent)

  Add `@classmethod from_transactions(cls, transactions, period_type, period_label, period_start, period_end, budget_data=None)` that:
  1. Filters expenses (amount < 0)
  2. Aggregates by `category_name` into `CategorySpending` list (reuse from `weekly_summary`)
  3. If `budget_data` is provided (list of dicts with `name`, `budgeted`, `activity`), builds `budget_comparison` list
  4. Returns populated `OnDemandSummary`
- **Tests:** `tests/test_on_demand_summary_model.py` — Test `from_transactions` with: no transactions, single category, multiple categories, budget comparison populated for monthly, budget comparison None for non-monthly, expense filtering (ignores positive amounts), correct sorting.

#### [x] Step 2: Application service — `OnDemandSummaryService`
- **Files:** `src/application/services/on_demand_summary_service.py`
- **Action:** Create `OnDemandSummaryService` class with:
  - `__init__(self, ynab_factory: YNABRepositoryFactory)` — takes factory only (no user_repository needed, read-only)
  - `generate_summary(self, user_config: UserConfiguration, period_type: str) -> OnDemandSummary`:
    1. Compute `period_start` and `period_end` based on `period_type` and `user_today(user_config.timezone)`:
       - "dia": today to today
       - "semana": Monday of current week to today
       - "mes": 1st of current month to today
    2. Fetch transactions via `ynab_factory.get_repository(user_config).get_transactions(budget_id, since_date=period_start.isoformat())`
    3. Filter transactions to only those within `[period_start, period_end]` by `date` field
    4. For "mes" period, also fetch categories via `get_categories(budget_id)` and build budget comparison data (active, non-hidden, non-deleted categories with budgeted > 0 or activity != 0)
    5. Build period label in Spanish:
       - "dia" -> "Hoy (DD/MM)"
       - "semana" -> "Semana (lun DD/MM - {weekday} DD/MM)"
       - "mes" -> "Mes de {month_name} {year}" (Spanish month names)
    6. Return `OnDemandSummary.from_transactions(...)`
  - `parse_period(self, args: str) -> str` — static/classmethod, parses user input to normalized period type. Accepts: "dia"/"día"/"hoy"/"today" -> "dia", "semana"/"week" -> "semana", "mes"/"month"/""(empty) -> "mes". Raises `ValueError` for unrecognized input.
- **Tests:** `tests/test_on_demand_summary_service.py` — Test: `parse_period` with all aliases and invalid input, `generate_summary` for each period type with mocked YNAB factory, date range computation for day/week/month, budget data fetched only for "mes", correct filtering of transactions to period range.

### Group 2 — Formatter (depends on: Group 1)

#### [x] Step 3: Telegram formatter — `OnDemandSummaryFormatter`
- **Files:** `src/presentation/telegram/formatters.py`
- **Action:** Add `OnDemandSummaryFormatter` class with static method `format_summary(summary: OnDemandSummary) -> str`:
  - If `not summary.has_transactions`: return friendly "No hubo gastos en {period_label}." message
  - Header: "📊 *Resumen — {period_label}*"
  - Total: "💰 *Total gastado:* ${total/1000:,.0f}"
  - Category breakdown section: "📋 *Desglose por categoría:*" followed by numbered list of ALL categories with amounts (same format as weekly summary top categories)
  - If `budget_comparison` is populated (monthly): add "📈 *Presupuesto vs. Gasto:*" section with each category showing budgeted, spent, remaining with color-coded emoji (green if remaining >= 0, red if overspent). Only show categories that have either budget or spending.
  - If period is not "mes": add footer note "💡 _La comparación con presupuesto está disponible con_ `/resumen mes`"
- **Tests:** `tests/test_on_demand_summary_formatter.py` — Test: no transactions message, day summary formatting, week summary formatting, month summary with budget comparison, month summary without budget data, category breakdown ordering, overspent category highlighting.

### Group 3 — Handler + Wiring (depends on: Group 2)

#### [x] Step 4: Telegram handler — `SummaryHandler`
- **Files:** `src/presentation/telegram/handlers/summary_handler.py`
- **Action:** Create `SummaryHandler(BaseHandler)` class with:
  - `__init__(self, container)`: call `super().__init__(container)`, store `self.summary_service = container.get_on_demand_summary_service()`, `self.auth_service = container.get_auth_service()`
  - `handle_resumen_command(self, update, context)`: decorated with `@require_authentication(lambda self: self.auth_service)`:
    1. Get user config from `auth_service.register_user(update.effective_user)`
    2. Check `user_config.is_configured()` — if not, reply with config instructions
    3. Parse period from `context.args` (join args, default to empty string)
    4. Call `summary_service.parse_period(period_arg)` — catch ValueError, reply with usage help
    5. Call `summary_service.generate_summary(user_config, period_type)`
    6. Format with `OnDemandSummaryFormatter.format_summary(summary)`
    7. Reply with formatted message (parse_mode='Markdown')
    8. Catch `YNABApiException` and `OAuthException` with appropriate error messages
  - `handle` method: delegate to `handle_resumen_command` (satisfies BaseHandler abstract method)
- **Tests:** `tests/test_summary_handler.py` — Test: successful summary for each period, unconfigured user gets config message, invalid period gets usage help, YNAB API error handled gracefully, OAuth error handled, no args defaults to month.

#### [x] Step 5: DI container registration
- **Files:** `src/infrastructure/container.py`
- **Action:**
  1. Add import: `from application.services.on_demand_summary_service import OnDemandSummaryService`
  2. In `_configure_services()`, register as transient (same pattern as `WeeklySummaryService`):
     ```python
     self.register_transient(
         OnDemandSummaryService,
         lambda: OnDemandSummaryService(
             ynab_factory=self.get(YNABRepositoryFactory),
         )
     )
     ```
  3. Add convenience method: `def get_on_demand_summary_service(self): return self.get(OnDemandSummaryService)`
- **Tests:** No new test file needed — existing container tests (if any) or the handler tests exercise wiring indirectly.

#### [x] Step 6: Bot command registration
- **Files:** `src/presentation/telegram/bot.py`
- **Action:**
  1. Import `SummaryHandler` from `presentation.telegram.handlers.summary_handler`
  2. In `__init__`, create `self.summary_handler = SummaryHandler(container)`
  3. In `_register_handlers`, add: `self.application.add_handler(CommandHandler("resumen", self.summary_handler.handle_resumen_command))`
  4. Place the registration in the "General commands" section, after `/help`
- **Tests:** No new test file needed — handler tests cover the logic. Bot registration is verified by the handler integration test.

### Group 4 — Help text update (depends on: Group 3)

#### [x] Step 7: Update help text and welcome message
- **Files:** `src/presentation/telegram/formatters.py`
- **Action:** In `GeneralResponseFormatter.format_command_list()`, add `/resumen` to the "Consultas" section:
  ```
  • `/resumen` - Resumen de gastos (dia/semana/mes)
  ```
- **Tests:** No dedicated test — existing formatter tests for help text can be extended if needed, or the code reviewer verifies the string is present.

## Constraints & Architecture
- **Milliunits invariant**: All amounts from YNAB are in milliunits (x1000). Display by dividing by 1000. Expenses are negative in YNAB — use `abs()` for display.
- **Per-user isolation**: All YNAB API calls go through `YNABRepositoryFactory.get_repository(user_config)` — never share repos across users.
- **UI language**: All user-facing strings must be in Spanish.
- **Dependency injection**: `OnDemandSummaryService` is registered as transient in `DIContainer`, resolved via factory pattern.
- **No DB changes**: This feature is purely API-driven. No migrations needed. DBA consultation not required.
- **Reuse `CategorySpending`**: Import from `domain.models.weekly_summary` rather than duplicating the dataclass.
- **YNAB API caching**: `YNABApiRepository` already caches categories and transactions for 5 minutes — no additional caching needed.

## Verification
- [x] `/resumen` (no args) shows current month summary with budget comparison
- [x] `/resumen dia` shows today's spending by category
- [x] `/resumen semana` shows current week spending by category
- [x] `/resumen mes` shows month summary with budget comparison section
- [x] Invalid period like `/resumen año` shows usage help message
- [x] Unauthenticated user gets auth required message
- [x] Unconfigured user (no budget) gets configuration instructions
- [x] User with no transactions in period sees friendly empty message
- [x] All amounts display correctly (milliunits -> display units)
- [x] Spanish month names display correctly (e.g., "Mes de marzo 2026")
