# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

YNAB Telegram Bot — a multi-user Telegram bot that logs expenses to YNAB (You Need A Budget) using OpenAI GPT-4o-mini for natural language parsing and Whisper for voice transcription. Targeted at Spanish-speaking users managing budgets in Colombian pesos. All UI text and prompts are in Spanish.

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Initialize project structure and data files
python setup.py

# Run the bot
python main.py

# Test individual modules (each has standalone test code in __main__)
python -m src.parsers.llm_expense_parser
python -m src.parsers.adaptive_category_learner
python -m src.integrations.ynab_category_manager
python -m src.integrations.ynab_account_manager
python -m src.integrations.speech_to_text
```

There is no formal test suite — modules have inline `if __name__ == "__main__"` test blocks.

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

### Legacy modules (still used by application services)

- **`src/parsers/`** — `LLMExpenseParser` (GPT-4o-mini), `SmartExpenseParser` (orchestrator), `AdaptiveCategoryLearner` (frequency-based learning). `expense_parser.py` is deprecated.
- **`src/integrations/`** — `ynab_client.py`, `ynab_category_manager.py`, `ynab_account_manager.py`, `speech_to_text.py`.

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

### Key Conventions

- YNAB amounts are in milliunits (×1000), negated for expenses
- Amount formats: `40000`, `40 mil`, `40 lucas`, `40k`, `$40000`, decimals with comma (`40000,50`)
- `main.py` adds `src/` to `sys.path`, so imports within `src/` use package names directly (e.g., `from domain.models.user import ...`)
- The `src/bot/telegram_bot.py` is a legacy bot class; the active one is `src/presentation/telegram/bot.py`
