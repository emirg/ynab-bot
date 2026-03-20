# Plan: Milestone 3.3 — Mejor Manejo de Errores

## Objective & Context
- **Status:** Completed
- **Goal:** Improve error handling across the bot with three pillars: (1) clear, actionable error messages in Spanish, (2) automatic retries for transient YNAB API errors (429, 500), and (3) structured logging for diagnostics.
- **Why:** Currently, error messages are generic and often expose internal details (e.g., raw exception strings). YNAB API transient failures cause immediate user-facing errors with no retry. Logging uses plain text with inconsistent formatting, making production diagnosis difficult.

## Current State Analysis

**Error messages today:**
- Handlers use generic catch-all messages like "Ocurrió un error procesando tu mensaje. Intenta de nuevo."
- `ExpenseService` catches domain exceptions and returns `str(e)` directly to the user — many of these are in English or contain technical details (e.g., "YNAB API error: Failed to get categories: ConnectionError...")
- `ExpenseResponseFormatter.format_error()` has keyword-based routing ("not configured", "parse", "ynab") but the match is fragile and doesn't cover all exception types.

**API resilience today:**
- `YNABApiRepository` makes raw `requests.*` calls with no timeout, no retries, and no rate-limit handling.
- `OAuthService._request_token()` uses `timeout=30` — the only place with a timeout.

**Logging today:**
- All modules use `logging.getLogger(__name__)` with `logging.basicConfig()` in `main.py`.
- Log format is plain text: `%(asctime)s - %(name)s - %(levelname)s - %(message)s`.
- No structured fields (user_id, operation, status_code, duration) — making log filtering/search in Railway very difficult.

## Affected Components

### New files
- `src/infrastructure/http_client.py` — Resilient HTTP client with retries and timeouts
- `tests/test_http_client.py` — Tests for retry logic
- `src/infrastructure/logging_config.py` — Structured logging configuration
- `tests/test_logging_config.py` — Tests for logging setup

### Modified files
- `src/domain/exceptions.py` — Add `is_retryable` property to `YNABApiException`, add `user_message` to all exceptions
- `src/infrastructure/repositories/ynab_api_repository.py` — Use resilient HTTP client instead of raw `requests`
- `src/application/services/oauth_service.py` — Use resilient HTTP client for token requests
- `src/presentation/telegram/formatters.py` — Refactor `format_error()` to use exception-type-based routing instead of string matching
- `src/presentation/telegram/handlers/base_handler.py` — Add structured context to error logging
- `src/presentation/telegram/handlers/expense_handler.py` — Use exception-aware error formatting
- `src/application/services/expense_service.py` — Attach Spanish user-facing messages to exceptions instead of raw `str(e)`
- `main.py` — Replace `logging.basicConfig()` with structured logging setup
- `tests/test_domain_exceptions.py` — Tests for new exception properties
- `tests/test_ynab_api_repository.py` — Tests for retry behavior
- `tests/test_formatters.py` — Tests for new error formatting logic
- `tests/test_expense_service.py` — Tests for user-facing error messages

## Prerequisites (Manual)
- [ ] None — no new env vars, API keys, or infrastructure needed

## Implementation Steps

### Group 1: Foundation — Exceptions & HTTP Client
<!-- Domain exceptions with user-facing messages + resilient HTTP client. No inter-dependencies. -->

#### [x] Step 1: Enhance domain exceptions with `user_message`
- **Files:** `src/domain/exceptions.py`
- **Action:**
  - Add a `user_message: str` field to `YNABBotException` base class (defaults to a generic Spanish message: "Ocurrió un error inesperado. Intenta de nuevo.").
  - Add `is_retryable: bool` property to `YNABApiException` — returns `True` when `status_code` is in `{429, 500, 502, 503, 504}` or `status_code is None` (network error).
  - Update each exception subclass to set a meaningful Spanish `user_message`:
    - `UserNotConfiguredException` → "No tienes tu presupuesto configurado. Usa /config para empezar."
    - `ExpenseParsingException` → "No pude entender tu mensaje. Intenta con un formato como: almuerzo 25000"
    - `YNABApiException` → "Hubo un problema conectando con YNAB. Intenta de nuevo en unos segundos."
    - `InvalidExpenseException` → "Los datos del gasto no son válidos. Revisa el monto e intenta de nuevo."
    - `OAuthException` → "Hubo un problema con la autenticación de YNAB. Intenta reconectar con /connect."
    - `TokenExpiredException` → "Tu sesión de YNAB expiró. Usa /connect para reconectar."
    - `SpeechProcessingException` → "No pude procesar el mensaje de voz. Intenta de nuevo o envía un texto."
    - `ImageProcessingException` → "No pude analizar la imagen. Asegúrate de que sea legible e intenta de nuevo."
    - `LearningDataException` → "Hubo un problema con el sistema de aprendizaje."
    - `ConfigurationException` → "Error de configuración del bot."
  - Preserve backward compatibility: existing `str(exception)` behavior unchanged.
- **Tests:** `tests/test_domain_exceptions.py` — Test `user_message` for each exception type, test `is_retryable` for various status codes (429 → True, 500 → True, 401 → False, None → True, 200 → False).

#### [x] Step 2: Create resilient HTTP client with retries
- **Files:** `src/infrastructure/http_client.py`
- **Action:**
  - Create `ResilientHTTPClient` class wrapping `requests.Session`.
  - Constructor params: `base_url: str`, `default_headers: dict`, `timeout: int = 15`, `max_retries: int = 3`, `retry_backoff_base: float = 1.0`.
  - Methods: `get(path, **kwargs)`, `post(path, **kwargs)`, `put(path, **kwargs)` — all return `requests.Response`.
  - Retry logic:
    - Retry on status codes 429, 500, 502, 503, 504.
    - Retry on `requests.exceptions.ConnectionError` and `requests.exceptions.Timeout`.
    - Exponential backoff: `retry_backoff_base * (2 ** attempt)` seconds, capped at 10s.
    - On 429: respect `Retry-After` header if present (parse as seconds), otherwise use backoff.
    - After all retries exhausted, raise `YNABApiException` with the last status code and response.
  - All requests include the configured timeout.
  - Log each retry attempt at WARNING level with structured info (attempt number, status code, wait time).
- **Tests:** `tests/test_http_client.py` — Test: (1) successful request no retry, (2) retry on 429 then success, (3) retry on 500 then success, (4) retry on ConnectionError then success, (5) all retries exhausted raises YNABApiException, (6) Retry-After header respected, (7) timeout passed to requests, (8) max retries configurable.

### Group 2: Structured Logging Setup
<!-- Depends on Group 1 only because logging_config is imported in main.py which also needs updated exceptions -->
<!-- Actually no dependency on Group 1's code — can run in parallel -->

#### [x] Step 3: Create structured logging configuration
- **Files:** `src/infrastructure/logging_config.py`
- **Action:**
  - Create `setup_logging(level: str = "INFO", json_format: bool = True)` function.
  - When `json_format=True` (production/Railway): use a custom `logging.Formatter` that outputs JSON with fields: `timestamp`, `level`, `logger`, `message`, `user_id` (if present in record), `operation` (if present), `duration_ms` (if present), `status_code` (if present), `error_type` (if present).
  - When `json_format=False` (local dev): use the current human-readable format.
  - Auto-detect: default to JSON if `RAILWAY_ENVIRONMENT` env var is set, otherwise human-readable.
  - Create `LogContext` — a context manager / helper that adds extra fields to log records within a scope. Implementation: use `logging.LoggerAdapter` or a simple function `log_with_context(logger, level, message, **extra)`.
  - Do NOT use any third-party logging library — keep it stdlib only.
- **Tests:** `tests/test_logging_config.py` — Test: (1) JSON formatter output is valid JSON with expected fields, (2) human-readable format matches current pattern, (3) extra fields (user_id, operation) appear in JSON output, (4) auto-detection of environment.

### Group 3: Wire HTTP Client into Repositories (depends on: Group 1)
<!-- Replace raw requests calls with the resilient client -->

#### [x] Step 4: Refactor `YNABApiRepository` to use `ResilientHTTPClient`
- **Files:** `src/infrastructure/repositories/ynab_api_repository.py`
- **Action:**
  - Change constructor to accept a `ResilientHTTPClient` instance instead of building raw headers.
  - Replace all `requests.get/post/put` calls with `self.client.get/post/put`.
  - Remove local `try/except requests.exceptions.RequestException` blocks — the client handles retries; repository still catches and wraps in `YNABApiException` but now the transient errors will have been retried first.
  - Update `YNABRepositoryFactory` to create `ResilientHTTPClient` and inject it into `YNABApiRepository`.
  - Add structured log context: include `operation` name (e.g., "get_categories", "create_transaction") in log calls.
- **Tests:** `tests/test_ynab_api_repository.py` — Update existing mocks to work with the new client. Add test: transient error retried before raising.

#### [x] Step 5: Refactor `OAuthService` to use `ResilientHTTPClient` for token requests
- **Files:** `src/application/services/oauth_service.py`
- **Action:**
  - Create a `ResilientHTTPClient` for OAuth token endpoint (base_url=`https://app.ynab.com`, max_retries=2).
  - Replace `requests.post` in `_request_token()` with client call.
  - Remove manual timeout — client handles it.
- **Tests:** `tests/test_oauth_service.py` — Verify retry on transient token endpoint failure.

### Group 4: Error Message Formatting (depends on: Group 1)
<!-- Improve user-facing error messages using the new exception.user_message -->

#### [x] Step 6: Refactor error formatting to use exception types
- **Files:** `src/presentation/telegram/formatters.py`
- **Action:**
  - Refactor `ExpenseResponseFormatter.format_error()`:
    - Accept an optional `exception` parameter alongside the existing `result` parameter.
    - When an exception is available, use `exception.user_message` as the primary message.
    - Keep the keyword-based routing as fallback for cases where only `error_message` string is available (backward compat).
    - Add specific formatting for `TokenExpiredException` — include `/connect` button suggestion.
    - Add specific formatting for rate-limit errors (429) — "YNAB está temporalmente ocupado. Intenta en unos segundos."
  - Ensure all error output is in Spanish and includes an actionable next step.
- **Tests:** `tests/test_formatters.py` — Test error formatting for each exception type, test fallback string matching, test 429-specific message.

#### [x] Step 7: Update `ExpenseService` to use `user_message` from exceptions
- **Files:** `src/application/services/expense_service.py`
- **Action:**
  - In `process_message()`, `process_expense_message()`, and `process_receipt_image()`: when catching domain exceptions, use `e.user_message` instead of `str(e)` for `ExpenseResult.error_result()`.
  - This ensures the user sees the clean Spanish message, not the technical English one.
  - Keep `logger.error(f"... {e}")` for the full technical details in logs.
- **Tests:** `tests/test_expense_service.py` — Test that `YNABApiException` returns `user_message` in result, not raw exception string.

### Group 5: Handler-Level Improvements (depends on: Group 1, Group 4)
<!-- Update handlers to use structured logging and improved error messages -->

#### [x] Step 8: Add structured logging context to `BaseHandler`
- **Files:** `src/presentation/telegram/handlers/base_handler.py`
- **Action:**
  - Update `log_handler_start`, `log_handler_error`, `log_handler_success` to include structured extra fields using the `log_with_context` helper from Step 3: `user_id`, `handler_name` as `operation`.
  - In `log_handler_error`: also include `error_type=type(error).__name__`.
  - Update `send_error_message` to accept an optional exception and use `exception.user_message` when available, falling back to the string parameter.
- **Tests:** Existing handler tests should continue passing. Add specific test in `tests/test_base_handler.py` (or existing handler test file) for the new `send_error_message` behavior with exception objects.

#### [x] Step 9: Update `ExpenseHandler` error handling
- **Files:** `src/presentation/telegram/handlers/expense_handler.py`
- **Action:**
  - In catch blocks for `handle_text_message`, `handle_voice_message`, `handle_photo_message`: pass the caught exception to `send_error_message` so it can use `user_message`.
  - For specific exception types that the handler catches directly (e.g., `SpeechProcessingException`, `ImageProcessingException`), use `e.user_message` instead of `str(e)`.
  - Remove hardcoded generic error strings where the exception already provides a better message.
- **Tests:** `tests/test_expense_handler.py` — Verify that YNAB API errors show the Spanish user_message, not the raw exception.

### Group 6: Wire Structured Logging in main.py (depends on: Group 2)

#### [x] Step 10: Replace `logging.basicConfig()` with structured setup
- **Files:** `main.py`
- **Action:**
  - Replace `logging.basicConfig(...)` with call to `setup_logging()` from `infrastructure.logging_config`.
  - Remove the manual format string.
  - Ensure Railway deployment gets JSON logs, local dev gets human-readable.
- **Tests:** No unit test needed — verified by existing test suite passing (logging setup shouldn't break anything). Manual verification step added below.

### Group 7: Integration & DI Wiring (depends on: Group 3, Group 5, Group 6)

#### [x] Step 11: Update `DIContainer` to wire `ResilientHTTPClient`
- **Files:** `src/infrastructure/container.py`
- **Action:**
  - Update `create_container()` to create `ResilientHTTPClient` instances for YNAB API and OAuth.
  - Pass the YNAB HTTP client to `YNABRepositoryFactory` so it can inject it into `YNABApiRepository`.
  - Pass the OAuth HTTP client to `YNABOAuthService`.
- **Tests:** `tests/test_container.py` (if exists) or `tests/test_integration.py` — Verify container creates components without error.

## Constraints & Architecture
- All user-facing text MUST be in Spanish (invariant).
- `YNABApiException.status_code` is already captured — leverage it for retry decisions.
- No new external dependencies — use stdlib `logging` and `requests` (already in requirements).
- Retry logic must NOT retry on 401 (unauthorized) or 400 (bad request) — these indicate user/client errors, not transient issues.
- The `ResilientHTTPClient` is a thin infrastructure wrapper — it must NOT contain business logic or domain knowledge.
- Structured logging must be backward compatible — existing `logger.info("message")` calls continue working, structured fields are optional extras.

## Verification
- [ ] All existing tests pass (~520 tests)
- [ ] Coverage remains at ~88%+
- [ ] Send a text expense while YNAB API is returning 500 → verify retry + eventual success or clean Spanish error
- [ ] Check Railway logs show JSON format with user_id and operation fields
- [ ] Verify `/connect` with expired token shows actionable Spanish message
- [ ] Verify parse failure shows helpful Spanish examples
