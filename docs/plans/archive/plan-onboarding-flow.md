# Plan: Guided Onboarding Flow (Milestone 1.1)

## Objective & Context
- **Status:** Completed
- **Harness Roadmap Marker:** 1.1
- **Goal:** Replace the current passive `/start` + `/help` with a guided onboarding flow that detects where the user is in the setup process (YNAB connected? budget selected? account configured?) and walks them through each step automatically. After OAuth callback, proactively send a Telegram message guiding the user to select their budget.
- **Why:** New users who run `/start` today get a static welcome message and no guidance on what to do next. They must discover `/connect`, `/budgets`, `/accounts` on their own. This causes drop-off.

## Prerequisites (Manual)
- [x] None — all infrastructure (OAuth, Telegram bot, SQLite) already exists.

## Design Decisions

### D1: Post-OAuth Telegram notification
The OAuth callback in `health.py` runs on a plain HTTP thread and has no access to the Telegram bot instance. To send a Telegram message after OAuth completes, we will:
- Pass a callable `on_oauth_success(telegram_user_id)` to the health module (mirroring the existing `set_oauth_service` pattern). The bot registers this callback at startup.
- **Chosen approach:** The callback uses `requests.post()` to call the Telegram Bot API directly (`https://api.telegram.org/bot<token>/sendMessage`), sending the post-OAuth message **with an inline keyboard for budget selection** serialized as JSON in the `reply_markup` parameter. This is fully synchronous and avoids event loop conflicts with the async `python-telegram-bot` library. The callback fetches budgets via `UserConfigService`, builds the keyboard dict using a shared serializer (see Step 5), and sends it in one API call.
- **Alternative considered:** Polling-based detection (check on next user interaction). Rejected because it breaks the "guided" promise — the user might not interact again for hours.
- **Alternative considered:** Sending a text-only message pointing to `/start`. Rejected in favor of sending the inline keyboard directly for a seamless experience.

### D2: Onboarding state detection logic
Rather than introducing a new "onboarding_step" column, we derive the step from existing data:
1. No YNAB token → guide to `/connect`
2. Has token, no `budget_id` → auto-show budget selection
3. Has token + `budget_id`, no `default_account_id` → auto-show account selection
4. Fully configured → show "ready to go" message with example

This keeps the data model unchanged and the logic purely presentational.

### D3: `/help` scope
`/help` will be restructured to show a concise command reference organized by category. It will remain behind `@require_authentication`. No new handler needed — just update `GeneralResponseFormatter.format_help_message()`.

## Implementation Steps
*(Models MUST mark steps with [x] as they are completed and save the file)*

### [x] Step 1: Create `OnboardingService` in application layer
- **Files:** `src/application/services/onboarding_service.py`
- **Action:** New service class `OnboardingService` with method `get_onboarding_step(telegram_user_id: int) -> OnboardingStep`. Returns an enum/dataclass indicating the user's current onboarding state: `NEEDS_YNAB_CONNECTION`, `NEEDS_BUDGET`, `NEEDS_ACCOUNT`, `COMPLETE`. Depends on `UserRepository` and checks `has_ynab_token()`, `budget_id`, `default_account_id`. This is a pure domain-state query — no side effects.
- **Tests:** `tests/test_onboarding_service.py` — Test all 4 states: user without token, user with token but no budget, user with token+budget but no account, fully configured user. Also test user-not-found case.

### [x] Step 2: Define `OnboardingStep` enum in domain layer
- **Files:** `src/domain/models/onboarding.py`
- **Action:** Create `OnboardingStep` enum with values: `NEEDS_YNAB_CONNECTION`, `NEEDS_BUDGET`, `NEEDS_ACCOUNT`, `COMPLETE`. Keep it minimal — just the enum, no logic.
- **Tests:** `tests/test_domain_models.py` — Add basic enum value tests (trivial, can be in existing file).

### [x] Step 3: Add onboarding-aware formatter methods
- **Files:** `src/presentation/telegram/formatters.py`
- **Action:** Add new methods to `GeneralResponseFormatter`:
  - `format_onboarding_welcome(user_name: str, step: OnboardingStep) -> str` — Returns the appropriate welcome message based on step. For `NEEDS_YNAB_CONNECTION`: welcome text + CTA to use `/connect`. For `NEEDS_BUDGET`: "Ya conectaste YNAB, ahora selecciona tu presupuesto:" (with instruction to wait for inline keyboard). For `NEEDS_ACCOUNT`: "Ahora selecciona tu cuenta por defecto:". For `COMPLETE`: "Ya estas listo! Proba enviando algo como: almuerzo 25000".
  - `format_post_oauth_message() -> str` — Message sent after OAuth success: "Cuenta YNAB conectada exitosamente! Ahora vamos a configurar tu presupuesto..."
  - `format_onboarding_complete() -> str` — Final congratulations message with usage example.
- **Tests:** `tests/test_formatters.py` — Test each formatter method returns Spanish strings with expected content for each step.

### [x] Step 4: Refactor `/start` handler to use onboarding flow
- **Files:** `src/presentation/telegram/handlers/general_handler.py`
- **Action:** Modify `handle_start_command` for authorized users:
  1. Inject/access `OnboardingService` and `UserConfigService` via container.
  2. After confirming user is authorized, call `onboarding_service.get_onboarding_step(user_id)`.
  3. Based on step:
     - `NEEDS_YNAB_CONNECTION` → Send welcome message with `/connect` CTA.
     - `NEEDS_BUDGET` → Send message + auto-trigger budget list with inline keyboard (reuse `ConfigHandler.handle_budgets_command` logic or call `user_config_service.get_available_budgets()` and build keyboard inline).
     - `NEEDS_ACCOUNT` → Send message + auto-trigger account list with inline keyboard.
     - `COMPLETE` → Send "ready" message with example.
  - The key architectural question: should `/start` directly build budget/account keyboards, or should it delegate to ConfigHandler? **Decision:** Build the keyboards directly in GeneralHandler to avoid cross-handler coupling. Extract the keyboard-building logic into a shared utility or the formatter.
- **Tests:** `tests/test_general_handler.py` (NEW file) — Test `/start` for each onboarding step with mocked OnboardingService and UserConfigService. Verify correct message and keyboard are sent for each state.

### [x] Step 5: Extract inline keyboard builders into shared utility
- **Files:** `src/presentation/telegram/keyboards.py` (NEW)
- **Action:** Extract budget selection keyboard and account selection keyboard building logic from `ConfigHandler` into standalone functions:
  - `build_budget_selection_keyboard(budgets: List[YNABBudget]) -> InlineKeyboardMarkup` — returns a `python-telegram-bot` `InlineKeyboardMarkup` for use in handlers.
  - `build_account_selection_keyboard(accounts: List[YNABAccount]) -> InlineKeyboardMarkup` — same pattern for accounts.
  - `budget_keyboard_to_dict(budgets: List[YNABBudget]) -> dict` — returns a plain dict serializable to JSON, structured as the Telegram Bot API `reply_markup` format: `{"inline_keyboard": [[{"text": "...", "callback_data": "select_budget_..."}], ...]}`. This is used by the post-OAuth sync callback (Step 7) which calls the raw Telegram API via `requests` and cannot use `InlineKeyboardMarkup`.
  - Refactor `ConfigHandler` to use the shared `build_*` functions (no behavior change).
  - Use the `InlineKeyboardMarkup` variants in `GeneralHandler` for onboarding, and the `_to_dict` variant in the post-OAuth callback.
- **Tests:** `tests/test_keyboards.py` (NEW) — Test keyboard builders produce correct button labels and callback data. Test `_to_dict` variant produces valid JSON-serializable structure matching Telegram API format. Test empty list case. Test 10-item limit.

### [x] Step 6: Register `OnboardingService` in DI container
- **Files:** `src/infrastructure/container.py`
- **Action:** Register `OnboardingService` as transient service with `UserRepository` dependency. Add convenience method `get_onboarding_service()`.
- **Tests:** No separate test needed — covered by integration in Step 4 tests.

### [x] Step 7: Implement post-OAuth Telegram notification with inline keyboard
- **Files:** `src/infrastructure/health.py`, `src/infrastructure/telegram_notifier.py` (NEW), `main.py`
- **Action:**
  1. **`health.py`:** Add a module-level `_on_oauth_success` callback variable (mirroring `_oauth_service`). Add `set_on_oauth_success(callback)` setter function. In `_handle_oauth_callback`, after successful `exchange_code_for_tokens`, extract `telegram_user_id` from the returned `UserConfiguration` and call `_on_oauth_success(telegram_user_id)` if the callback is set. Wrap the call in try/except so callback failures never break the OAuth HTML response.
  2. **`telegram_notifier.py` (NEW):** Create a lightweight `TelegramNotifier` class that sends messages via the raw Telegram Bot API using `requests`. Constructor takes `bot_token: str`. Key method:
     - `send_message(chat_id: int, text: str, parse_mode: str = 'Markdown', reply_markup: dict = None)` — POSTs to `https://api.telegram.org/bot{token}/sendMessage` with JSON body `{"chat_id": ..., "text": ..., "parse_mode": ..., "reply_markup": ...}`. Returns `True` on success, `False` on failure (logs the error). This is fully synchronous — safe to call from the health server thread.
     - This class is intentionally minimal and infrastructure-only. It does NOT depend on `python-telegram-bot`.
  3. **`main.py`:** After creating the DI container and bot, build the post-OAuth callback:
     - Instantiate `TelegramNotifier(config.telegram_token)`.
     - Define `on_oauth_success(telegram_user_id: int)`:
       a. Fetch budgets via `container.get_user_config_service().get_available_budgets(telegram_user_id)`.
       b. Build the inline keyboard dict using `budget_keyboard_to_dict(budgets)` from Step 5.
       c. Format the message text using `GeneralResponseFormatter.format_post_oauth_message()` from Step 3.
       d. Call `notifier.send_message(chat_id=telegram_user_id, text=message, reply_markup=keyboard_dict)`.
       e. **Graceful degradation:** If budget fetch fails (e.g., YNAB rate limit), send a text-only fallback: "Cuenta YNAB conectada. Usa /start para continuar con la configuracion."
     - Register via `set_on_oauth_success(on_oauth_success)`.
  4. **Error handling:** All failures in the callback are logged but never raised. The user always sees the HTML success page regardless. If the Telegram message fails to send, the user can recover via `/start` which will detect the `NEEDS_BUDGET` state.
- **Tests:**
  - `tests/test_telegram_notifier.py` (NEW) — Test `TelegramNotifier.send_message()` with mocked `requests.post`: verify correct URL (`/bot<token>/sendMessage`), verify JSON body includes `chat_id`, `text`, `parse_mode`, and `reply_markup` dict. Test failure case returns `False` and logs error.
  - `tests/test_health.py` — Add test for OAuth callback triggering `_on_oauth_success` with correct `telegram_user_id`. Mock the callback and verify it is called exactly once on success, and not called on OAuth failure.

### [x] Step 8: Enhance post-budget-selection to auto-show accounts
- **Files:** `src/presentation/telegram/handlers/config_handler.py`
- **Action:** In `handle_callback_query`, after `select_budget_` succeeds, instead of just showing "Ahora configura tu cuenta con `/accounts`", automatically fetch accounts and show the inline keyboard. Use shared keyboard builder from Step 5. This makes the flow seamless: select budget -> immediately see accounts.
- **Tests:** `tests/test_config_handler.py` (NEW or extend existing) — Test that selecting a budget triggers account keyboard display.

### [x] Step 9: Enhance post-account-selection to show onboarding complete
- **Files:** `src/presentation/telegram/handlers/config_handler.py`
- **Action:** After `select_account_` succeeds, send the `format_onboarding_complete()` message that includes a usage example: "Ahora proba enviando algo como: almuerzo 25000". Use the formatter from Step 3.
- **Tests:** Same test file as Step 8 — verify the completion message content.

### [x] Step 10: Restructure `/help` command
- **Files:** `src/presentation/telegram/formatters.py`
- **Action:** Rewrite `GeneralResponseFormatter.format_help_message()` to be more structured:
  - Group commands by category: Configuracion, Gastos, Consultas, Aprendizaje
  - Include brief description per command
  - Add section for natural language examples (text, voice, photo)
  - Keep it concise — avoid wall of text
  - Ensure it includes `/connect`, `/disconnect` which are currently missing from help
- **Tests:** `tests/test_formatters.py` — Update existing help message tests to verify new structure contains all command categories.

### [x] Step 11: Update unknown command handler
- **Files:** `src/presentation/telegram/handlers/general_handler.py`
- **Action:** Update `handle_unknown_command` to use the same command list as `/help` for consistency. Extract the command list to a shared constant or formatter method to avoid duplication. Add `/connect` and `/disconnect` to the list.
- **Tests:** `tests/test_general_handler.py` — Verify unknown command response includes `/connect`.

## Constraints & Architecture
- All user-facing strings MUST be in Spanish.
- `OnboardingService` must use `UserRepository` (DI, not direct DB access).
- Post-OAuth notification uses sync HTTP (not async Telegram bot) to avoid event loop conflicts in the health server thread.
- Budget/account keyboard builders are pure functions — no side effects, easy to test.
- No database migrations needed — onboarding state is derived from existing columns.
- `@require_authentication` remains on `/help` and expense handlers. `/start` stays unauthenticated (it handles its own auth checks).
- The inline keyboard callback patterns (`select_budget_*`, `select_account_*`) remain unchanged — the existing `ConfigHandler.handle_callback_query` already handles them.

## Risks & Open Questions
1. **Post-OAuth message delivery timing:** The Telegram `sendMessage` call from the health thread is fire-and-forget. If the user's Telegram client is offline, the message will be delivered later by Telegram's infrastructure. No retry needed on our side.
2. **Budget fetch failure after OAuth:** If fetching budgets fails immediately after OAuth (e.g., rate limit), the post-OAuth message should gracefully degrade to "Usa /start para continuar con la configuracion" instead of showing an error.
3. **~~Inline keyboard in post-OAuth~~ (RESOLVED):** Decided to send the inline keyboard via raw `requests` POST to the Telegram API. Step 5 adds a `budget_keyboard_to_dict()` helper that produces the plain-dict format required by the raw API. Step 7 introduces `TelegramNotifier` to encapsulate this call.
4. **Multiple `/start` invocations:** The onboarding flow should be idempotent. Running `/start` multiple times at any stage should re-detect the current state and show the appropriate step, never corrupt data.

## Verification
- [x] New user runs `/start` -> sees welcome + prompted to `/connect`
- [x] User completes OAuth -> receives Telegram message with budget selection inline keyboard (sent via raw API)
- [x] User selects budget -> immediately sees account list
- [x] User selects account -> sees "ready" message with usage example
- [x] User runs `/start` again after full setup -> sees "already configured" message
- [x] `/help` shows organized command reference
- [x] User without YNAB token runs `/start` -> guided to `/connect` (not generic welcome)
- [x] All tests pass, coverage does not drop below 86%

## Review Notes (2026-03-14)
Reviewed by Claude Code (Lead Architect). All 11 steps verified against implementation.

**Minor observations (non-blocking):**
- Step 11 test for `handle_unknown_command` including `/connect` was not added to `test_general_handler.py`. Coverage is indirectly provided by `test_formatters.py` testing `format_command_list()`.
- `format_welcome_message()` is now unused dead code (replaced by `format_onboarding_welcome()`). Consider removing in a future cleanup.
- `pytest.ini` coverage scope does not include `keyboards.py` or handler files from `presentation/telegram/`. Pre-existing gap, not a regression.
