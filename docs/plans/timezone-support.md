# Plan: Timezone-Aware Date Handling

## Objective & Context
- **Status:** In Progress
- **Goal:** Fix the timezone bug where transactions get tomorrow's date when users interact with the bot after 21:00 local time (Argentina, UTC-3) because the Railway server runs in UTC.
- **Why:** `datetime.now()` is called without timezone info in 3 locations that affect user-facing date logic. After 21:00 ART (00:00+ UTC), the bot assigns the next day's date to transactions and misreports "today" in date comparisons. Internal bookkeeping timestamps (user.py `created_at`/`updated_at`) are fine as UTC and should NOT be touched.

## Affected Components
- `src/domain/models/expense.py` — Expense default date uses `datetime.now()` (line 30)
- `src/parsers/llm_expense_parser.py` — `_get_date_context()` uses `datetime.now()` (line 106)
- `src/presentation/telegram/formatters.py` — `_format_date_line()` compares against `date.today()` (line 19)
- `src/domain/time_utils.py` — **NEW** central time helper module
- `src/infrastructure/repositories/database_manager.py` — migration v7 to add `timezone` column
- `src/infrastructure/repositories/sqlite_user_repository.py` — persist/load timezone field
- `src/domain/models/user.py` — add `timezone` field to `UserConfiguration`
- `src/application/services/user_config_service.py` — add `update_timezone()` method
- `src/presentation/telegram/handlers/config_handler.py` — add `/zona` command handler
- `src/presentation/telegram/bot.py` — register `/zona` command
- `tests/test_time_utils.py` — **NEW** tests for time helper
- `tests/test_domain_models.py` — update Expense tests for timezone-aware dates
- `tests/test_llm_expense_parser.py` — update date context tests
- `tests/test_formatters.py` — update date line tests
- `tests/test_expense_service.py` — update date handling tests
- `tests/test_user_config_service.py` — test timezone update
- `tests/test_config_handler.py` — test `/zona` command

## Prerequisites (Manual)
- [ ] None (uses stdlib `zoneinfo`, no new dependencies)

## Implementation Steps
*(Models MUST mark steps with [x] as they are completed and save the file)*

### Group 1: DBA Consultation
<!-- Validate migration and schema design before any implementation -->

#### [x] Step 1: DBA Review of timezone column migration
- **Files:** `src/infrastructure/repositories/database_manager.py`
- **Action:** Consult `dba-advisor` on adding a `timezone TEXT DEFAULT 'America/Argentina/Buenos_Aires'` column to `user_configurations` as migration v7. Confirm: column type, default value, index necessity, migration safety.
- **Tests:** N/A (advisory step)

### Group 2: Domain time helper + UserConfiguration model (depends on: Group 1)
<!-- Build the foundational pieces: central time utility and the model field. No file overlap. -->

#### [x] Step 2: Create `src/domain/time_utils.py` — central timezone helper
- **Files:** `src/domain/time_utils.py`
- **Action:** Create a new module with:
  - `DEFAULT_TIMEZONE = "America/Argentina/Buenos_Aires"` constant
  - `def user_now(timezone_str: str = DEFAULT_TIMEZONE) -> datetime` — returns timezone-aware `datetime.now()` for the given IANA timezone string. Uses `zoneinfo.ZoneInfo`. If the timezone string is invalid, falls back to `DEFAULT_TIMEZONE` and logs a warning.
  - `def user_today(timezone_str: str = DEFAULT_TIMEZONE) -> date` — returns `user_now(timezone_str).date()`. Convenience for date-only comparisons.
  - All returned datetimes MUST be timezone-aware (have `tzinfo` set).
- **Tests:** `tests/test_time_utils.py` —
  - `test_user_now_returns_aware_datetime` — result has non-None `tzinfo`
  - `test_user_now_default_timezone` — default is Argentina
  - `test_user_now_custom_timezone` — passing "UTC" returns UTC time
  - `test_user_now_invalid_timezone_falls_back` — invalid string falls back to default
  - `test_user_today_returns_date` — returns a `date` object
  - `test_user_now_utc_minus_3_difference` — at a known UTC time, Argentina is 3 hours behind

#### [x] Step 3: Add `timezone` field to `UserConfiguration`
- **Files:** `src/domain/models/user.py`
- **Action:** Add `timezone: str = "America/Argentina/Buenos_Aires"` field to the `UserConfiguration` dataclass, after the `last_name` field and before `created_at`. Import `DEFAULT_TIMEZONE` from `domain.time_utils` and use it as the default value. Add a method `def update_timezone(self, timezone: str)` that sets `self.timezone = timezone` and updates `self.updated_at`.
- **Tests:** `tests/test_domain_models.py` —
  - `test_user_configuration_default_timezone` — new user has default timezone
  - `test_user_configuration_update_timezone` — `update_timezone()` sets value and updates `updated_at`

### Group 3: Database migration + Repository (depends on: Group 2)
<!-- Persist the timezone field. Both files are independent of each other at this stage. -->

#### [x] Step 4: Add migration v7 for timezone column
- **Files:** `src/infrastructure/repositories/database_manager.py`
- **Action:** Add migration v7 to `_MIGRATIONS` list: `ALTER TABLE user_configurations ADD COLUMN timezone TEXT DEFAULT 'America/Argentina/Buenos_Aires';`. Follow exact pattern of existing migrations (tuple of version, description, SQL).
- **Tests:** `tests/test_database_manager.py` — test that migration v7 applies cleanly on a fresh DB and that the column exists with the correct default.

#### [x] Step 5: Persist and load `timezone` in `SQLiteUserRepository`
- **Files:** `src/infrastructure/repositories/sqlite_user_repository.py`
- **Action:** Update `_row_to_user_config()` to read the `timezone` column from the DB row and set it on `UserConfiguration`. Update `save()` / upsert SQL to include the `timezone` column. If the column value is `None` or empty in the DB, default to `DEFAULT_TIMEZONE`.
- **Tests:** `tests/test_sqlite_user_repository.py` —
  - `test_save_and_load_timezone` — save a user with custom timezone, reload, verify it persists
  - `test_default_timezone_on_load` — user without timezone column value gets default

### Group 4: Fix the 3 bug locations (depends on: Group 2)
<!-- Each file is independent. All three consume `time_utils` but don't touch each other. -->

#### [x] Step 6: Fix Expense model default date
- **Files:** `src/domain/models/expense.py`
- **Action:** Change the `date` field default from `default_factory=datetime.now` to `default_factory=lambda: None`. The date will be set explicitly by the caller (ExpenseService) using the user's timezone. When `date` is `None`, `to_ynab_format()` should use `datetime.now()` as a fallback for the date string (defensive, should not normally happen). Update the import to include `Optional` if not already. The `date` field type changes to `Optional[datetime]` with default `None`.
- **Tests:** `tests/test_domain_models.py` —
  - `test_expense_default_date_is_none` — new Expense() has date=None
  - `test_expense_to_ynab_format_with_none_date_uses_today` — defensive fallback works

#### [x] Step 7: Fix LLM date context
- **Files:** `src/parsers/llm_expense_parser.py`
- **Action:** Change `_get_date_context()` from `@staticmethod` to a regular method. Add a `timezone` parameter: `def _get_date_context(self, timezone_str: str = DEFAULT_TIMEZONE) -> str`. Use `user_now(timezone_str)` instead of `datetime.now()`. Update all callers within the class (`_generate_system_prompt`, `_generate_receipt_system_prompt`, `_generate_message_system_prompt`) to accept and pass through a `timezone_str` parameter. Add `timezone_str` parameter to `parse_message()`, `parse_expense()`, and `parse_receipt_image()` public methods (default: `DEFAULT_TIMEZONE`), flowing it through to prompt generation.
- **Tests:** `tests/test_llm_expense_parser.py` —
  - `test_get_date_context_uses_timezone` — mock `user_now` to a known datetime, verify the context string contains the correct date
  - `test_get_date_context_default_timezone` — without param, uses Argentina timezone

#### [x] Step 8: Fix formatter date comparison
- **Files:** `src/presentation/telegram/formatters.py`
- **Action:** Change `_format_date_line()` to accept a `user_tz: str = DEFAULT_TIMEZONE` parameter. Replace `date.today()` with `user_today(user_tz)`. Update `format_success()` to accept and pass through `user_tz`. Import `user_today` and `DEFAULT_TIMEZONE` from `domain.time_utils`.
- **Tests:** `tests/test_formatters.py` —
  - `test_format_date_line_uses_user_timezone` — with a mocked timezone, verify correct "today" comparison
  - `test_format_success_passes_timezone` — verify the timezone flows through

### Group 5: Wire timezone through the call chain (depends on: Groups 3, 4)
<!-- These steps connect the pieces: service reads user timezone and passes it to parser/formatter. -->

#### [x] Step 9: Pass timezone through ExpenseService
- **Files:** `src/application/services/expense_service.py`
- **Action:** In `process_message()`, `process_expense_message()`, and `process_receipt_image()`: after loading `user_config`, extract `user_tz = user_config.timezone`. Pass `timezone_str=user_tz` to all `self.llm_parser.parse_message()`, `self.llm_parser.parse_expense()`, `self.llm_parser.parse_receipt_image()` calls. In `_build_expense_from_parsed()`: when the LLM returns `date: null` (no explicit date in message), set `expense.date = user_now(user_tz)` instead of relying on the old `datetime.now()` default. Add `user_tz` parameter to `_build_expense_from_parsed()`. Import `user_now` and `DEFAULT_TIMEZONE` from `domain.time_utils`.
- **Tests:** `tests/test_expense_service.py` —
  - `test_process_message_passes_timezone_to_parser` — verify llm_parser.parse_message is called with timezone_str
  - `test_build_expense_uses_user_timezone_for_default_date` — when LLM returns no date, expense.date uses user's timezone

#### [x] Step 10: Add `update_timezone()` to `UserConfigService`
- **Files:** `src/application/services/user_config_service.py`
- **Action:** Add method `def update_timezone(self, telegram_user_id: int, timezone_str: str) -> UserConfiguration`. Validate that `timezone_str` is a valid IANA timezone using `zoneinfo.ZoneInfo(timezone_str)` — raise `ValueError` with a Spanish message if invalid. Load user config, call `user_config.update_timezone(timezone_str)`, save, and return. Add timezone to the dict returned by `get_user_status()`.
- **Tests:** `tests/test_user_config_service.py` —
  - `test_update_timezone_valid` — sets timezone and saves
  - `test_update_timezone_invalid` — raises ValueError for bad timezone
  - `test_get_user_status_includes_timezone` — status dict contains timezone

### Group 6: Telegram command + bot registration (depends on: Group 5)
<!-- UI layer. Both files are independent. -->

#### [x] Step 11: Add `/zona` command handler
- **Files:** `src/presentation/telegram/handlers/config_handler.py`
- **Action:** Add an async `zona_command` handler method. If called without arguments (`/zona`), reply with the user's current timezone. If called with an argument (`/zona America/Bogota`), call `user_config_service.update_timezone()`. On success, reply in Spanish confirming the change. On `ValueError`, reply with the error. Add timezone info to the status display if it exists in this handler.
- **Tests:** `tests/test_config_handler.py` —
  - `test_zona_command_shows_current` — `/zona` without args shows current timezone
  - `test_zona_command_updates` — `/zona America/Bogota` updates and confirms
  - `test_zona_command_invalid` — `/zona Invalid/Zone` returns error

#### [x] Step 12: Register `/zona` in bot.py
- **Files:** `src/presentation/telegram/bot.py`
- **Action:** Add `zona` to the command handler registration, pointing to `config_handler.zona_command`. Follow the same pattern as other command registrations.
- **Tests:** Manual verification (bot registration is integration-level)

### Group 7: Wire timezone to formatter in handler (depends on: Group 6)
<!-- Final wiring: pass timezone from handler to formatter -->

#### [x] Step 13: Pass timezone to formatter in ExpenseHandler
- **Files:** `src/presentation/telegram/handlers/expense_handler.py`
- **Action:** In `handle_text_message()`, `handle_voice_message()`, and `handle_photo_message()`: after getting the expense result, load the user's timezone from `user_config_service` or `user_repository` and pass it to `ExpenseResponseFormatter.format_success(result, user_tz=tz)`. This ensures the "today" comparison in the formatter uses the correct timezone.
- **Tests:** `tests/test_expense_handler.py` —
  - `test_handle_text_message_passes_timezone_to_formatter` — verify formatter receives timezone

### Group 8: Update help text (depends on: Group 6)
<!-- Update Spanish UI text to mention /zona -->

#### [x] Step 14: Add `/zona` to help and command list
- **Files:** `src/presentation/telegram/formatters.py`
- **Action:** Add `/zona` to the command list in `GeneralResponseFormatter.format_command_list()` under the Configuration section: `"/zona - Cambiar zona horaria"`. Also update `format_help_message()` if needed.
- **Tests:** `tests/test_formatters.py` —
  - `test_command_list_includes_zona` — verify `/zona` appears in command list

## Constraints & Architecture
- **Do NOT touch** `user.py` timestamps (`created_at`, `updated_at`, `approved_at`, `ynab_token_expires_at`) — these are internal bookkeeping and UTC is correct for them.
- `zoneinfo.ZoneInfo` is stdlib (Python 3.9+), no new deps needed.
- All user-facing strings MUST be in Spanish.
- `time_utils` lives in `src/domain/` because it's a pure domain concern (no infrastructure deps).
- The `Expense.date` field changes from "always has a value" to "None means not yet assigned" — callers MUST set it explicitly via `user_now()`.
- Existing tests that create `Expense()` objects may need minor updates since `date` default changes from `datetime.now()` to `None`.

## Verification
- [ ] All existing tests pass (no regressions from date default change)
- [ ] New tests cover: time helper, timezone persistence, LLM context, formatter comparison, service wiring
- [ ] Manual test: set Railway server to UTC, send expense at 22:00 ART — verify transaction date is today (not tomorrow)
- [ ] Manual test: `/zona` shows current timezone
- [ ] Manual test: `/zona America/Bogota` changes timezone and subsequent expenses use it
- [ ] Coverage remains at ~88%+
