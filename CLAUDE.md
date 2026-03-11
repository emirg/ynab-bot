# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

YNAB Telegram Bot — a multi-user Telegram bot that logs expenses to YNAB (You Need A Budget) using OpenAI GPT-4o-mini for natural language parsing and Whisper for voice transcription. Each user connects their own YNAB account via OAuth. Targeted at Spanish-speaking users managing budgets in Colombian pesos. All UI text and prompts are in Spanish.

## Session Initialization
Whenever you start a new session or the user asks you to "resume", your VERY FIRST action MUST be to read `docs/wip_state.md`. This file will contain information in case Gemini CLI did some changes or completed a task while you were away.
There will be 5 scenarios:
- If the file indicates that Gemini completed a task, you must acknowledge it, read the details, and continue from there.
- If the file indicates that Gemini did not complete a task, you must continue from where you left off.
- If the file has the content you wrote in the latest handoff, asume Gemini CLI did not worked while you were away and you must continue from where you left off.
- If the file is empty, you must continue from where you left off.
- If the file does not exist, you must continue from where you left off.

## Plans
- Every time a plan is created, save it to `docs/plans/` and update `CLAUDE.md` to reference it.
- Once you finish implementing a plan, move the plan to `docs/plans/archive/` and update `CLAUDE.md` to reference it.

### Feature Planning Protocol
Whenever I ask you to create a plan for a new feature or refactor, you MUST use the structure defined in `docs/plans/_TEMPLATE.md`. 
Create the new plan file in the `docs/plans/` directory. Break down the implementation into atomic, sequential steps, always specifying the exact file paths for both the implementation and its corresponding tests.

## Commands

```bash
# Setup virtualenv and install dependencies
python -m venv .venv
source .venv/bin/activate  # or: source .venv/bin/activate.fish
pip install -r requirements.txt

# Run the bot
python main.py

# Run full test suite (~349 tests, ~86% coverage)
pytest

# Run a single test file
pytest tests/test_domain_models.py

# Run a single test class or method
pytest tests/test_domain_models.py::TestExpense::test_is_valid_basic

# Run tests with keyword filter
pytest -k "test_predict_category"
```

## Architecture

Layered architecture with dependency injection:

```
main.py → health server (port $PORT) → DIContainer (infrastructure/container.py) → YNABTelegramBot (presentation/telegram/bot.py)
```

### Layers

- **`src/domain/`** — Domain models (`Expense`, `UserConfiguration`, `YNABCategory`, `YNABAccount`, `YNABBudget`, `BudgetQueryResult`, `MessageResult`), repository interfaces (abstract base classes), `AuthorizationService`, `payee_normalizer`, and custom exceptions. No external dependencies.
- **`src/application/services/`** — Business logic orchestrators. `ExpenseService` coordinates the full parse→enhance→create→learn pipeline and routes between expenses and budget queries via `process_message()`. `BudgetQueryService` handles category balance, account balance, and budget summary queries. `UserConfigService` manages per-user YNAB budget/account configuration. `YNABOAuthService` handles the full OAuth lifecycle (auth URLs, token exchange, refresh, disconnect). `LearningService` wraps the learning repository.
- **`src/infrastructure/`** — Concrete implementations. `DatabaseManager` (centralized SQLite connection, WAL mode, versioned migrations), `SQLiteUserRepository` (user persistence with token encryption), `SQLiteLearningRepository` (per-user learning data), `YNABApiRepository` (YNAB REST API), `YNABRepositoryFactory` (creates per-user YNAB repos from OAuth tokens), `TokenEncryptor` (Fernet encryption for tokens at rest), `health.py` (HTTP health check + OAuth callback endpoint). `AppConfig` loads from `config/.env`. `DIContainer` wires everything together.
- **`src/presentation/telegram/`** — Telegram bot and handlers. `bot.py` registers all command/message handlers. Handlers: `GeneralHandler`, `ConfigHandler` (includes `/connect`, `/disconnect`), `ExpenseHandler`, `LearningHandler`, `AdminHandler`. Auth via `@require_authentication` and `@require_admin` decorators.

### Supporting modules

- **`src/parsers/llm_expense_parser.py`** — `LLMExpenseParser` (GPT-4o-mini), used by `ExpenseService` via DI. `parse_message()` classifies intent (expense vs query) in a single LLM call; the LLM performs semantic matching to map user terms (e.g., "comida") to exact YNAB category names (e.g., "🛒 Groceries") using up to 100 categories in the prompt. `parse_expense()` is retained for backward compatibility (voice handler).
- **`src/integrations/speech_to_text.py`** — Whisper-based voice transcription, used by `ExpenseHandler` via DI.

### Data Flow

```
User (text) → ExpenseHandler.handle_text_message()
  → ExpenseService.process_message()
    → LLMExpenseParser.parse_message() → classifies intent ("expense" | "query")
    → if intent == "expense": existing expense pipeline (parse→enhance→create→learn)
    → if intent == "query": BudgetQueryService.execute_query()
      → category_balance | account_balance | budget_summary
  → BudgetQueryFormatter or ExpenseResponseFormatter → Telegram response

User (voice) → ExpenseHandler.handle_voice_message()
  → speech_to_text.py (Whisper)
  → ExpenseService.process_expense_message() → existing expense pipeline
```

### Per-User YNAB OAuth

Each user connects their own YNAB account. No shared global token.

```
User → /connect → generate OAuth URL with HMAC-signed state
     → YNAB authorization page → redirect to /oauth/callback
     → exchange code for tokens → encrypt & store in SQLite
     → YNABRepositoryFactory creates per-user YNABApiRepository on each request
```

- **Token lifecycle**: auto-refresh when expired (5-min buffer), Fernet-encrypted at rest in SQLite
- **State security**: HMAC-SHA256 signed with `YNAB_CLIENT_SECRET` to prevent CSRF
- **OAuth callback**: served by the health check HTTP server at `/oauth/callback`

### User Authentication

Multi-user system with admin approval. Users have statuses: `PENDING` → `AUTHORIZED` or `BLOCKED`. Admins are configured via `ADMIN_IDS` env var (required). Admin commands: `/admin`, `/pending`, `/users`, `/approve`, `/block`.

### Configuration

Environment variables loaded from `config/.env` (see `config/.env.example`):
- `TELEGRAM_BOT_TOKEN`, `OPENAI_API_KEY`, `ADMIN_IDS` (required)
- `YNAB_CLIENT_ID`, `YNAB_CLIENT_SECRET`, `YNAB_REDIRECT_URI` (OAuth, required)
- `TOKEN_ENCRYPTION_KEY` (Fernet key for encrypting OAuth tokens, required)
- `DATABASE_PATH` (default: `data/users.db`) — single SQLite database for users and learning data

### Deployment

Hosted on Railway. CI pipeline runs tests on build — if any test fails, deploy is cancelled.

```toml
# railway.toml
[build]
buildCommand = "pip install -r requirements.txt && pytest"
[deploy]
startCommand = "python main.py"
healthcheckPath = "/"
healthcheckTimeout = 30
restartPolicyType = "ON_FAILURE"
restartPolicyMaxRetries = 3
```

Health check server runs on `$PORT` (default 8080), serves `/` for Railway health checks and `/oauth/callback` for YNAB OAuth.

### Testing

- **Framework**: pytest with fixtures in `tests/conftest.py`, coverage via pytest-cov
- **Config**: `pytest.ini` scopes coverage to `src/domain`, `src/application`, `src/infrastructure`, and `src/presentation/telegram/formatters.py`
- **Conventions**: Shared fixtures for domain models, mock repositories (`mock_ynab_factory`, `mock_oauth_service`, `mock_user_repository`, `mock_learning_repository`, `mock_llm_parser`, `mock_budget_query_service`), and temp files in `conftest.py`. Tests use `unittest.mock.MagicMock`. `conftest.py` adds `src/` to `sys.path`.
- **Coverage**: ~86% on active architecture. Domain layer at 100%.

### Key Conventions

- YNAB amounts are in milliunits (×1000), negated for expenses
- Amount formats: `40000`, `40 mil`, `40 lucas`, `40k`, `$40000`, decimals with comma (`40000,50`)
- `main.py` adds `src/` to `sys.path`, so imports within `src/` use package names directly (e.g., `from domain.models.user import ...`)
- Pre-compiled regex patterns are module-level constants (e.g., `_UUID_PATTERN`, `_SPECIAL_CHARS_PATTERN`)
- Category and account lookups use O(1) dict maps built in `_update_llm_parser_data()`
- Query matching uses a two-tier approach: LLM performs semantic matching (user term → exact YNAB name), then `BudgetQueryService` applies 4-step fuzzy matching as fallback (exact → case-insensitive → clean/no-emoji → partial)
- YNAB API responses are cached with 5-minute TTL in `YNABApiRepository`
- YNAB services use `YNABRepositoryFactory` (not a singleton repo) — always resolve per-user via `factory.get_repository(user_config)`
- SQLite migrations are versioned in `database_manager.py` `_MIGRATIONS` list (currently at v3)

## Handoff Protocol
If you receive the explicit command "prepare handoff", "save state", or if I indicate that we are approaching the rate limit, you must stop writing new code immediately.

Your only task will be to create or overwrite the `docs/wip_state.md` file strictly using this structure:
- Make clear you (Claude Code) were the last one to work on the code.
- **Current Objective:** [1 or 2 lines describing the feature or bug we are currently working on. If you were working on a plan, reference that plan file you are using, and be specific about what you have completed so far]
- **Last Action:** [What was the last thing you did before stopping. Be specific]
- **Modified Files:** [List of file paths with unsaved changes. If no files are modified, write "None"]
- **Current State / Blocker:** [The exact terminal error, exception, or specific logic that is left to complete]
- **Next Step:** [The exact, technical instruction that the next AI must execute to resume the work]