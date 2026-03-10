# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

YNAB Telegram Bot — a multi-user Telegram bot that logs expenses to YNAB (You Need A Budget) using OpenAI GPT-4o-mini for natural language parsing and Whisper for voice transcription. Targeted at Spanish-speaking users managing budgets in Colombian pesos. All UI text and prompts are in Spanish.

## Commands

```bash
# Setup virtualenv and install dependencies
python -m venv .venv
source .venv/bin/activate  # or: source .venv/bin/activate.fish
pip install -r requirements.txt

# Initialize project structure and data files
python setup.py

# Run the bot
python main.py

# Run full test suite (263 tests, ~84% coverage)
pytest

# Run a single test file
pytest tests/test_domain_models.py

# Run a single test class or method
pytest tests/test_domain_models.py::TestExpense::test_is_valid_basic

# Run tests with keyword filter
pytest -k "test_predict_category"
```

## Architecture

The codebase uses a layered architecture with dependency injection:

```
main.py → DIContainer (infrastructure/container.py) → YNABTelegramBot (presentation/telegram/bot.py)
```

### Layers

- **`src/domain/`** — Domain models (`Expense`, `UserConfiguration`, `YNABCategory`, `YNABAccount`, `YNABBudget`), repository interfaces (abstract base classes), `AuthorizationService`, and custom exceptions. No external dependencies.
- **`src/application/services/`** — Business logic orchestrators. `ExpenseService` coordinates the full parse→enhance→create→learn pipeline. `UserConfigService` manages per-user YNAB budget/account configuration. `LearningService` wraps the learning repository.
- **`src/infrastructure/`** — Concrete implementations. `SQLiteUserRepository` (user persistence in `data/users.db`), `YNABApiRepository` (YNAB REST API), `JSONLearningRepository` (learning data in JSON). `AppConfig` loads from `config/.env`. `DIContainer` wires everything together with singleton/transient registrations.
- **`src/presentation/telegram/`** — Telegram bot and handlers. `bot.py` registers all command/message handlers. Handlers are split by concern: `GeneralHandler`, `ConfigHandler`, `ExpenseHandler`, `LearningHandler`, `AdminHandler`. Auth is enforced via decorators in `middleware/auth_middleware.py` (`@require_authentication`, `@require_admin`).

### Supporting modules

- **`src/parsers/llm_expense_parser.py`** — `LLMExpenseParser` (GPT-4o-mini), used by `ExpenseService` via DI.
- **`src/integrations/speech_to_text.py`** — Whisper-based voice transcription, used by `ExpenseHandler` via DI.

### Data Flow

```
User (text/voice) → presentation/telegram/handlers/expense_handler.py
  → speech_to_text.py (if voice, via Whisper)
  → ExpenseService.process_expense_message()
    → LLMExpenseParser (GPT-4o-mini: extract amount, category, payee, account)
    → LearningRepository.predict_category() (frequency-based, confidence ≥0.6)
    → YNABApiRepository.create_transaction()
    → LearningRepository.record_successful_transaction()
```

### User Authentication

Multi-user system with admin approval. Users have statuses: `PENDING` → `AUTHORIZED` or `BLOCKED`. Admins are configured via `ADMIN_IDS` env var (required). Admin commands: `/admin`, `/pending`, `/users`, `/approve`, `/block`.

### Configuration

Environment variables loaded from `config/.env` (see `config/.env.example`):
- `TELEGRAM_BOT_TOKEN`, `YNAB_ACCESS_TOKEN`, `YNAB_BUDGET_ID`, `OPENAI_API_KEY`
- `ADMIN_IDS` (required, comma-separated Telegram user IDs)
- `DATABASE_PATH` (default: `data/users.db`), `LEARNING_DATA_PATH` (default: `data/category_learning_data.json`)

### Testing

- **Framework**: pytest with fixtures in `tests/conftest.py`, coverage via pytest-cov
- **Config**: `pytest.ini` scopes coverage to `src/domain`, `src/application`, `src/infrastructure`, and `src/presentation/telegram/formatters.py`
- **Conventions**: Shared fixtures for domain models, mock repositories, and temp files in `conftest.py`. Tests use `unittest.mock.MagicMock` for repository/parser mocks. `conftest.py` adds `src/` to `sys.path`.
- **Coverage**: ~84% on active architecture. Domain layer at 100%.

### Key Conventions

- YNAB amounts are in milliunits (×1000), negated for expenses
- Amount formats: `40000`, `40 mil`, `40 lucas`, `40k`, `$40000`, decimals with comma (`40000,50`)
- `main.py` adds `src/` to `sys.path`, so imports within `src/` use package names directly (e.g., `from domain.models.user import ...`)
- Pre-compiled regex patterns are module-level constants (e.g., `_UUID_PATTERN`, `_SPECIAL_CHARS_PATTERN`)
- Category lookups use O(1) dict maps built in `_update_llm_parser_data()`
- YNAB API responses are cached with 5-minute TTL in `YNABApiRepository`
