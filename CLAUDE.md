# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

YNAB Telegram Bot — a multi-user Telegram bot that logs expenses to YNAB (You Need A Budget) using OpenAI GPT-4o-mini for natural language parsing and Whisper for voice transcription. Each user connects their own YNAB account via OAuth. Targeted at Spanish-speaking users managing budgets in Colombian pesos. All UI text and prompts are in Spanish.

## Commands

```bash
# Setup virtualenv and install dependencies
python -m venv .venv
source .venv/bin/activate  # or: source .venv/bin/activate.fish
pip install -r requirements.txt

# Run the bot
python main.py

# Run full test suite (~297 tests, ~85% coverage)
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

- **`src/domain/`** — Domain models (`Expense`, `UserConfiguration`, `YNABCategory`, `YNABAccount`, `YNABBudget`), repository interfaces (abstract base classes), `AuthorizationService`, `payee_normalizer`, and custom exceptions. No external dependencies.
- **`src/application/services/`** — Business logic orchestrators. `ExpenseService` coordinates the full parse→enhance→create→learn pipeline. `UserConfigService` manages per-user YNAB budget/account configuration. `YNABOAuthService` handles the full OAuth lifecycle (auth URLs, token exchange, refresh, disconnect). `LearningService` wraps the learning repository.
- **`src/infrastructure/`** — Concrete implementations. `DatabaseManager` (centralized SQLite connection, WAL mode, versioned migrations), `SQLiteUserRepository` (user persistence with token encryption), `SQLiteLearningRepository` (per-user learning data), `YNABApiRepository` (YNAB REST API), `YNABRepositoryFactory` (creates per-user YNAB repos from OAuth tokens), `TokenEncryptor` (Fernet encryption for tokens at rest), `health.py` (HTTP health check + OAuth callback endpoint). `AppConfig` loads from `config/.env`. `DIContainer` wires everything together.
- **`src/presentation/telegram/`** — Telegram bot and handlers. `bot.py` registers all command/message handlers. Handlers: `GeneralHandler`, `ConfigHandler` (includes `/connect`, `/disconnect`), `ExpenseHandler`, `LearningHandler`, `AdminHandler`. Auth via `@require_authentication` and `@require_admin` decorators.

### Supporting modules

- **`src/parsers/llm_expense_parser.py`** — `LLMExpenseParser` (GPT-4o-mini), used by `ExpenseService` via DI.
- **`src/integrations/speech_to_text.py`** — Whisper-based voice transcription, used by `ExpenseHandler` via DI.

### Data Flow

```
User (text/voice) → ExpenseHandler
  → speech_to_text.py (if voice)
  → ExpenseService.process_expense_message()
    → YNABRepositoryFactory.get_repository(user_config)  ← per-user OAuth token
    → LLMExpenseParser (GPT-4o-mini: extract amount, category, payee, account)
    → LearningRepository.predict_category() (frequency-based, confidence ≥0.6)
    → YNABApiRepository.create_transaction()
    → LearningRepository.record_successful_transaction()
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
- **Conventions**: Shared fixtures for domain models, mock repositories (`mock_ynab_factory`, `mock_oauth_service`, `mock_user_repository`, `mock_learning_repository`, `mock_llm_parser`), and temp files in `conftest.py`. Tests use `unittest.mock.MagicMock`. `conftest.py` adds `src/` to `sys.path`.
- **Coverage**: ~85% on active architecture. Domain layer at 100%.

### Key Conventions

- YNAB amounts are in milliunits (×1000), negated for expenses
- Amount formats: `40000`, `40 mil`, `40 lucas`, `40k`, `$40000`, decimals with comma (`40000,50`)
- `main.py` adds `src/` to `sys.path`, so imports within `src/` use package names directly (e.g., `from domain.models.user import ...`)
- Pre-compiled regex patterns are module-level constants (e.g., `_UUID_PATTERN`, `_SPECIAL_CHARS_PATTERN`)
- Category and account lookups use O(1) dict maps built in `_update_llm_parser_data()`
- YNAB API responses are cached with 5-minute TTL in `YNABApiRepository`
- YNAB services use `YNABRepositoryFactory` (not a singleton repo) — always resolve per-user via `factory.get_repository(user_config)`
- SQLite migrations are versioned in `database_manager.py` `_MIGRATIONS` list (currently at v3)
