# Plan: Weekly Summary (Resumen Semanal)

## Objective & Context
- **Status:** Completed
- **Harness Roadmap Marker:** 3.4
- **Goal:** Automatically send each registered user a weekly spending summary every Monday at 8am (in their timezone), covering total spending, top 3 categories, and a week-over-week percentage comparison.
- **Why:** Users currently have no passive insight into their spending patterns. A weekly summary provides proactive value without requiring user action, aligning with roadmap item 3.4 (Resumen Periodico).

## Architecture Decisions

### Scheduling: `python-telegram-bot` JobQueue vs. standalone scheduler

**Decision: Use `run_repeating` with a 15-minute tick + manual timezone-aware check.**

Rationale:
- `run_daily` only accepts a single `datetime.time` with one timezone. Since users have different timezones, we cannot use one `run_daily` per timezone (they are dynamic and per-user).
- Scheduling one `run_daily` per user is fragile (jobs lost on restart, must sync with DB).
- A single repeating "tick" job (every 15 minutes) that checks "which users should receive their summary right now?" is simpler, stateless, and robust:
  - On each tick: get all authorized+configured users, compute their local time, check if it's Monday between 08:00-08:14, and if they haven't already received a summary this week, send it.
  - A `last_weekly_summary_sent` timestamp column in the user table prevents duplicates.
- This is the same pattern used by production bots and avoids APScheduler complexity.
- Trade-off: 15-minute granularity means the message arrives between 8:00-8:14. Acceptable for a weekly digest.

### Data Source: YNAB Transactions API

- Endpoint: `GET /v1/budgets/{budget_id}/transactions?since_date=YYYY-MM-DD`
- Returns all transactions from `since_date` onward. We fetch from `monday_of_previous_week` and client-side filter to the exact Mon-Sun range.
- For the comparison, we also need the week before that, so `since_date` = two Mondays ago.
- Transaction fields used: `amount` (milliunits, negative = expense), `category_name`, `date`.

### Error Isolation

- Each user is processed in its own try/except. A failure (expired token, API error, etc.) logs the error and continues to the next user.
- The tick job itself has a top-level try/except so a bug never crashes the bot.

### Message Formatting

- All text in Spanish.
- If no transactions: "No hubo movimientos esta semana."
- Amounts formatted in pesos (divided by 1000 from milliunits).

## Affected Components

- `src/domain/repositories/ynab_repository.py` -- add `get_transactions(budget_id, since_date)` abstract method
- `src/infrastructure/repositories/ynab_api_repository.py` -- implement `get_transactions`
- `src/domain/models/weekly_summary.py` -- new domain model `WeeklySummary`
- `src/application/services/weekly_summary_service.py` -- new service: compute summary from transactions
- `src/presentation/telegram/formatters.py` -- add `WeeklySummaryFormatter`
- `src/infrastructure/repositories/database_manager.py` -- migration v6: add `last_weekly_summary_sent` column
- `src/infrastructure/repositories/sqlite_user_repository.py` -- read/write new column
- `src/domain/models/user.py` -- add `last_weekly_summary_sent` field
- `src/presentation/telegram/bot.py` -- register the tick job on startup
- `src/infrastructure/scheduler.py` -- new module: tick job logic (which users, when to send)
- `src/infrastructure/container.py` -- wire `WeeklySummaryService`
- `tests/test_weekly_summary_service.py` -- unit tests for summary computation
- `tests/test_weekly_summary_formatter.py` -- unit tests for message formatting
- `tests/test_scheduler.py` -- unit tests for tick logic (timezone checks, deduplication)
- `tests/test_ynab_api_repository.py` -- tests for `get_transactions`

## Prerequisites (Manual)
- [x] Install APScheduler dependency: `pip install "python-telegram-bot[job-queue]"` and update `requirements.txt` (APScheduler is required by PTB's JobQueue)

## Implementation Steps

### Group 1: DBA Consultation
<!-- Database schema change needs DBA review before implementation -->

#### [x] Step 1: DBA Review — Migration v8
- **Action:** Consult `dba-advisor` on adding `last_weekly_summary_sent` (TEXT, nullable, ISO datetime) column to `user_configurations` table. Migration v8 (not v6 — v7 already exists): `ALTER TABLE user_configurations ADD COLUMN last_weekly_summary_sent TEXT`. Reversible via `ALTER TABLE ... DROP COLUMN` (SQLite 3.35+). No index needed.
- **DBA findings:** Use TEXT type, store always in UTC (`datetime.now(timezone.utc).isoformat()`), no index (PK access only), method name `mark_weekly_summary_sent()` for consistency.

### Group 2: Domain & Repository Layer (depends on: Group 1)
<!-- New domain model + repository interface extension. No file conflicts — parallel safe. -->

#### [x] Step 2: Domain Model — `WeeklySummary`
- **Files:** `src/domain/models/weekly_summary.py`
- **Action:** Create dataclass `WeeklySummary` with fields:
  - `total_spent: int` (milliunits, always positive for display)
  - `category_breakdown: List[CategorySpending]` (category_name, amount — sorted desc by amount)
  - `top_categories: List[CategorySpending]` (top 3 from above)
  - `previous_week_total: int` (milliunits, for comparison)
  - `percentage_change: Optional[float]` (None if previous week had no spending)
  - `has_transactions: bool`
  - `week_start: date`
  - `week_end: date`
  - Helper dataclass `CategorySpending(category_name: str, amount: int)`.
  - Factory method `from_transactions(current_week_txns, previous_week_txns, week_start, week_end)` that computes all derived fields.
- **Tests:** `tests/test_weekly_summary_model.py` — Test: empty transactions, single transaction, multiple categories, top 3 selection, percentage change calculation (increase, decrease, no previous), negative amounts handling (expenses are negative in YNAB).

#### [x] Step 3: Repository Interface — `get_transactions`
- **Files:** `src/domain/repositories/ynab_repository.py`
- **Action:** Add abstract method `get_transactions(self, budget_id: str, since_date: str) -> List[dict]`. Returns raw transaction dicts with at least `amount`, `category_name`, `date`, `deleted`, `payee_name` fields. Using `List[dict]` (not a domain model) to keep the scope minimal — the service layer will filter and aggregate.
- **Tests:** No direct tests needed (abstract method). Covered by implementation tests.

#### [x] Step 4: Repository Implementation — `get_transactions`
- **Files:** `src/infrastructure/repositories/ynab_api_repository.py`
- **Action:** Implement `get_transactions` in `YNABApiRepository`:
  - `GET /v1/budgets/{budget_id}/transactions?since_date={since_date}`
  - Parse response: `response.json()["data"]["transactions"]`
  - Filter out deleted transactions (`deleted == True`)
  - No caching (this data changes frequently and is called weekly)
  - Follow existing error handling pattern (catch `RequestException`, raise `YNABApiException`)
- **Tests:** `tests/test_ynab_api_repository.py` — Add tests for `get_transactions`: mock the HTTP call, verify since_date parameter, verify deleted filtering, verify error handling.

### Group 3: Database Migration & User Model (depends on: Group 1)
<!-- Separate group from Group 2 because Group 4 depends on both Groups 2 and 3. These two groups have no file overlap so they can run in parallel. -->

#### [x] Step 5: Migration v8 — `last_weekly_summary_sent` column
- **Files:** `src/infrastructure/repositories/database_manager.py`
- **Action:** Add migration v8 to `_MIGRATIONS` list: `ALTER TABLE user_configurations ADD COLUMN last_weekly_summary_sent TEXT`. Follow existing migration pattern (list of SQL strings).
- **Tests:** `tests/test_database_manager.py` — Test migration v8 applies cleanly on a fresh DB and on an existing v7 DB.

#### [x] Step 6: User Model — `last_weekly_summary_sent` field
- **Files:** `src/domain/models/user.py`
- **Action:** Add `last_weekly_summary_sent: Optional[datetime] = None` field to `UserConfiguration`. Add method `mark_weekly_summary_sent()` that sets the field to `datetime.now(timezone.utc)` and updates `updated_at`.
- **Tests:** `tests/test_domain_models.py` — Test the new field default, test `mark_weekly_summary_sent` sets both fields.

#### [x] Step 7: User Repository — Read/Write new column
- **Files:** `src/infrastructure/repositories/sqlite_user_repository.py`
- **Action:** Update `_row_to_user_config` to read `last_weekly_summary_sent` (ISO parse, nullable). Update `save` to include the column in INSERT and ON CONFLICT UPDATE.
- **Tests:** `tests/test_sqlite_user_repository.py` — Test round-trip: save user with `last_weekly_summary_sent`, read back, verify value. Test null case.

### Group 4: Application Service (depends on: Groups 2, 3)
<!-- Service depends on domain model (Group 2) and will be used by scheduler which needs user model (Group 3) -->

#### [x] Step 8: `WeeklySummaryService`
- **Files:** `src/application/services/weekly_summary_service.py`
- **Action:** Create service with dependencies: `ynab_factory: YNABRepositoryFactory`, `user_repository: UserRepository`.
  - Method `generate_summary(user_config: UserConfiguration) -> WeeklySummary`:
    - Compute date range using `user_today(user_config.timezone)`: previous Monday to Sunday.
    - Also compute the week before for comparison.
    - Call `ynab_repo.get_transactions(budget_id, since_date=two_mondays_ago)`.
    - Split transactions into current week and previous week by date.
    - Filter to expenses only (amount < 0).
    - Build and return `WeeklySummary.from_transactions(...)`.
  - Method `should_send_summary(user_config: UserConfiguration) -> bool`:
    - Check: user is authorized, configured (budget + account), has YNAB token.
    - Check: user's local time is Monday between 08:00-08:14.
    - Check: `last_weekly_summary_sent` is None or older than 6 days (prevents duplicates).
  - Method `mark_summary_sent(user_config: UserConfiguration)`:
    - Set `last_weekly_summary_sent` to now, save via repository.
- **Tests:** `tests/test_weekly_summary_service.py` — Test `generate_summary` with mock YNAB repo returning sample transactions. Test `should_send_summary` for various conditions (not Monday, already sent, not configured, correct Monday 8am). Test date range computation across timezone boundaries.

### Group 5: Formatter (depends on: Group 2)
<!-- Depends on WeeklySummary domain model from Group 2. No overlap with Group 4 files. -->

#### [x] Step 9: `WeeklySummaryFormatter`
- **Files:** `src/presentation/telegram/formatters.py`
- **Action:** Add class `WeeklySummaryFormatter` with static methods:
  - `format_summary(summary: WeeklySummary) -> str`:
    - If `not summary.has_transactions`: return friendly "No hubo movimientos la semana pasada (lun {start} - dom {end}). A seguir ahorrando!"
    - Otherwise:
      ```
      📊 *Resumen semanal* (lun {start} - dom {end})

      💰 *Total gastado:* ${total:,.0f}

      📋 *Top categorias:*
      1. {cat1} — ${amount1:,.0f}
      2. {cat2} — ${amount2:,.0f}
      3. {cat3} — ${amount3:,.0f}

      📈 Gastaste {X}% mas/menos que la semana pasada.
      ```
    - If no previous week data: omit the comparison line.
    - Date format: `DD/MM` (e.g., "10/03 - 16/03").
    - All amounts divided by 1000 from milliunits.
- **Tests:** `tests/test_weekly_summary_formatter.py` — Test: full summary with comparison, no transactions, no previous week, single category, special characters in category names.

### Group 6: Scheduler & Wiring (depends on: Groups 4, 5)
<!-- Scheduler uses the service (Group 4) and formatter (Group 5). Also touches bot.py and container.py. -->

#### [x] Step 10: Scheduler Module
- **Files:** `src/infrastructure/scheduler.py`
- **Action:** Create module with async function:
  - `async def weekly_summary_tick(context: ContextTypes.DEFAULT_TYPE)`:
    - Retrieve `DIContainer` from `context.bot_data["container"]`.
    - Get all users via `user_repository.find_by_status(UserStatus.AUTHORIZED)`.
    - For each user, wrapped in individual try/except:
      - Call `service.should_send_summary(user)`. Skip if False.
      - Call `service.generate_summary(user)`.
      - Format with `WeeklySummaryFormatter.format_summary(summary)`.
      - Send via `context.bot.send_message(chat_id=user.telegram_id, text=message, parse_mode='Markdown')`.
      - Call `service.mark_summary_sent(user)`.
    - Log: number of users processed, successes, failures.
  - Top-level try/except around the entire function — log and swallow to never crash the bot.
- **Tests:** `tests/test_scheduler.py` — Test with mock container, mock users (various states), verify correct users receive messages, verify errors for one user don't block others, verify `mark_summary_sent` called on success only.

#### [x] Step 11: DI Container — Register `WeeklySummaryService`
- **Files:** `src/infrastructure/container.py`
- **Action:** Register `WeeklySummaryService` as transient (like other application services). Add convenience method `get_weekly_summary_service()`.
- **Tests:** Covered by existing container tests pattern. Add a simple test that `get_weekly_summary_service()` returns an instance.

#### [x] Step 12: Bot Startup — Register Tick Job
- **Files:** `src/presentation/telegram/bot.py`
- **Action:**
  - In `__init__` or a new `_register_jobs` method called from `__init__`:
    - Store `container` in `application.bot_data["container"]` (so tick job can access DI).
    - Call `self.application.job_queue.run_repeating(weekly_summary_tick, interval=900, first=10, name="weekly_summary_tick")` (900s = 15 min, first=10s delay after startup).
  - Import `weekly_summary_tick` from `infrastructure.scheduler`.
- **Tests:** `tests/test_bot.py` — Verify that after bot init, a job named `weekly_summary_tick` exists in the job queue.

### Group 7: Dependency Update (depends on: none — can run any time)
<!-- Independent task, no code file overlap -->

#### [x] Step 13: Update `requirements.txt`
- **Files:** `requirements.txt`
- **Action:** Ensure APScheduler is available. Check if `python-telegram-bot[job-queue]` is needed or if `python-telegram-bot==22.6` already includes it. If not, either add `APScheduler>=3.10` or change the PTB line to `python-telegram-bot[job-queue]==22.6`. Run `pip install` and verify import works.
- **Tests:** Verify `from telegram.ext import JobQueue` does not raise ImportError.

## Constraints & Architecture
- **Milliunits**: All YNAB amounts are in milliunits (x1000). Expenses are negative. The service must negate when computing "total spent" for display.
- **Per-user isolation**: Each user's YNAB data fetched via `YNABRepositoryFactory.get_repository(user_config)`. Never shared.
- **Dependency injection**: `WeeklySummaryService` receives its dependencies via constructor. Registered in `DIContainer`.
- **UI language**: All user-facing strings in Spanish.
- **Error isolation**: Per-user try/except in the tick function. One user's failure must not affect others.
- **Idempotency**: `last_weekly_summary_sent` column prevents sending duplicate summaries if the tick runs multiple times on Monday morning.
- **Timezone handling**: Use existing `user_now(user_config.timezone)` and `user_today(user_config.timezone)` from `domain.time_utils`.
- **No new external dependencies** beyond what PTB's job-queue extra requires (APScheduler).

## Verification
- [x] Run full test suite: `pytest` — all existing tests still pass
- [x] Verify migration v6 applies cleanly: create fresh DB, confirm `last_weekly_summary_sent` column exists
- [x] Manual test: temporarily set tick interval to 30s and `should_send_summary` to always return True. Confirm message arrives in Telegram.
- [x] Manual test: verify the message renders correctly in Telegram (Markdown formatting, peso amounts)
- [x] Manual test: kill and restart the bot — verify the tick job re-registers and no duplicate summaries are sent
- [x] Verify coverage remains >= 86%
