# Architecture

YNAB Telegram Bot — a multi-user Telegram bot that logs expenses to YNAB (You Need A Budget) using OpenAI GPT-4o-mini for natural language parsing and Whisper for voice transcription. Each user connects their own YNAB account via OAuth. Targeted at Spanish-speaking users managing budgets in Colombian pesos. All UI text and prompts are in Spanish.

Layered architecture with dependency injection:

```
main.py → health server (port $PORT) → DIContainer (infrastructure/container.py) → YNABTelegramBot (presentation/telegram/bot.py)
```

## Layers

- **`src/domain/`** — Domain models (`Expense`, `UserConfiguration`, `YNABCategory`, `YNABAccount`, `YNABBudget`, `BudgetQueryResult`, `MessageResult`, `OnboardingStep`, `SplitGroup`, `SharedAccountConfig`, `WeeklySummary`, `OnDemandSummary`), repository interfaces (abstract base classes), `AuthorizationService`, `payee_normalizer`, `time_utils` (timezone-aware date helpers), and custom exceptions. No external dependencies.
- **`src/application/services/`** — Business logic orchestrators. `ExpenseService` coordinates the full prepare→commit pipeline (parse→enhance, then create→learn) and routes between expenses and budget queries via `process_message()`. Supports confirmation mode: when enabled, `prepare_expense()` returns a preview without committing, and `commit_expense()` finalizes after user confirmation. `BudgetQueryService` handles category balance, account balance, and budget summary queries. `UserConfigService` manages per-user YNAB budget/account configuration, timezone, and confirmation mode. `YNABOAuthService` handles the full OAuth lifecycle (auth URLs, token exchange, refresh, disconnect). `LearningService` wraps the learning repository and provides dashboard/forget/stats methods. `OnboardingService` derives the user's onboarding state from existing fields (no DB column). `SplitConfigService` manages split group configuration, person aliases, and shared account settings — validates against YNAB API before persisting. `WeeklySummaryService` fetches YNAB transactions for the past week and computes per-category spending totals. `OnDemandSummaryService` provides day/week/month spending summaries with category breakdowns.
- **`src/infrastructure/`** — Concrete implementations. `DatabaseManager` (centralized SQLite connection, WAL mode, versioned migrations — currently at v9), `SQLiteUserRepository` (user persistence with token encryption), `SQLiteLearningRepository` (per-user learning data), `SQLiteSplitConfigRepository` (split groups, aliases, shared account), `YNABApiRepository` (YNAB REST API), `YNABRepositoryFactory` (creates per-user YNAB repos from OAuth tokens), `TokenEncryptor` (Fernet encryption for tokens at rest), `health.py` (HTTP health check + OAuth callback endpoint, fires `on_oauth_success` callback after token exchange), `TelegramNotifier` (sync HTTP wrapper for raw Telegram Bot API — used in post-OAuth callback to avoid async event loop conflicts), `scheduler.py` (weekly summary tick job, runs every 15 minutes, checks per-user timezone to fire on Monday 8am local time), `http_client.py` (resilient HTTP client with automatic retries for transient errors), `logging_config.py` (structured logging setup). `AppConfig` loads from `config/.env`. `DIContainer` wires everything together.
- **`src/presentation/telegram/`** — Telegram bot and handlers. `bot.py` registers all command/message handlers and the weekly summary scheduler job. Handlers: `GeneralHandler` (includes guided onboarding via `OnboardingService`), `ConfigHandler` (includes `/connect`, `/disconnect`, `/zona` for timezone), `ExpenseHandler` (handles text/voice/photo expenses, `/confirmacion on|off`, and confirmation callbacks), `LearningHandler` (includes `/aprendizaje`, `/olvidar`, `/deshacer`, `/editar`), `SplitConfigHandler` (`/splitwise` — split group CRUD, alias management, shared account config via inline keyboards with pagination), `SummaryHandler` (`/resumen` — on-demand spending summary), `AdminHandler`. `keyboards.py` provides shared inline keyboard builders (confirmation keyboard, budget/account selection, split config panels with pagination). Auth via `@require_authentication` and `@require_admin` decorators.

## Supporting Modules

- **`src/parsers/llm_expense_parser.py`** — `LLMExpenseParser` (GPT-4o-mini), used by `ExpenseService` via DI. `parse_message()` classifies intent (`expense` | `query` | `shared_expense`) in a single LLM call; the LLM performs semantic matching to map user terms (e.g., "comida") to exact YNAB category names (e.g., "🛒 Groceries") using up to 100 categories in the prompt. Also extracts optional `date` field (relative or absolute, resolved to `YYYY-MM-DD`) and shared expense fields (`person`, `proportion`, `payer`). `parse_receipt_image()` handles vision-based receipt extraction using the same JSON output format. `parse_expense()` is retained for backward compatibility (voice handler).
- **`src/integrations/speech_to_text.py`** — Whisper-based voice transcription, used by `ExpenseHandler` via DI.

## Data Flow

```
User (text) → ExpenseHandler.handle_text_message()
  → ExpenseService.process_message()
    → LLMExpenseParser.parse_message() → classifies intent ("expense" | "query" | "shared_expense")
    → if intent == "expense":
      → prepare phase: parse→enhance (builds expense object)
      → if confirmation_mode ON: store in context.user_data["pending_expense"], show preview with inline keyboard
      → if confirmation_mode OFF: auto-commit → create→learn
    → if intent == "shared_expense":
      → resolve split group & person alias
      → if payer == "user": subtransactions (real category + split tracking category)
      → if payer == "other": zero-sum transaction (outflow + inflow balance to $0)
      → create→learn
    → if intent == "query": BudgetQueryService.execute_query()
      → category_balance | account_balance | budget_summary
  → BudgetQueryFormatter or ExpenseResponseFormatter → Telegram response

User (confirmation callback) → ExpenseHandler.handle_confirmation_callback()
  → retrieve pending_expense from context.user_data
  → if confirmed: commit_expense() → create→learn
  → if cancelled: discard pending expense

User (voice) → ExpenseHandler.handle_voice_message()
  → speech_to_text.py (Whisper)
  → ExpenseService.process_expense_message() → existing expense pipeline

User (photo) → ExpenseHandler.handle_photo_message()
  → download + base64 encode (max 5MB)
  → ExpenseService.process_receipt_image()
    → LLMExpenseParser.parse_receipt_image() → vision extraction (amount, payee, items→memo)
    → existing expense pipeline (enhance→create→learn), parser_source='receipt'
  → ExpenseResponseFormatter → Telegram response

Weekly summary (scheduler) → weekly_summary_tick()
  → for each user: check timezone, if Monday 8am local → WeeklySummaryService → send summary via Telegram
```

## Per-User YNAB OAuth

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

## Shared Expenses

Split expenses use YNAB subtransactions to track debts via a dedicated Splitwise tracking category.

- **User-paid split**: Transaction with two subtransactions — user's share goes to the real category, the other person's share goes to the split tracking category.
- **Third-party paid split** (zero-sum): Transaction amount is `$0` with two subtransactions — outflow from real category balanced by inflow to split tracking category. Uses the shared tracking account configured via `/splitwise`.
- **100% debt**: When `proportion=1` and `payer=other`, user owes the full amount (e.g., "Juan pagó el mercado por mí").
- **Configuration**: `SplitConfigService` manages split groups (linked to YNAB categories), person aliases, and shared account — validates against YNAB API before persisting. Data stored in `split_groups`, `split_person_aliases`, and `split_shared_account` SQLite tables.

## User Authentication

Multi-user system with admin approval. Users have statuses: `PENDING` → `AUTHORIZED` or `BLOCKED`. Admins are configured via `ADMIN_IDS` env var (required). Admin commands: `/admin`, `/pending`, `/users`, `/approve`, `/block`.

## Configuration

Environment variables loaded from `config/.env` (see `config/.env.example`):
- `TELEGRAM_BOT_TOKEN`, `OPENAI_API_KEY`, `ADMIN_IDS` (required)
- `YNAB_CLIENT_ID`, `YNAB_CLIENT_SECRET`, `YNAB_REDIRECT_URI` (OAuth, required)
- `TOKEN_ENCRYPTION_KEY` (Fernet key for encrypting OAuth tokens, required)
- `DATABASE_PATH` (default: `data/users.db`) — single SQLite database for users and learning data

## Deployment

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

## Testing

- **Framework**: pytest with fixtures in `tests/conftest.py`, coverage via pytest-cov
- **Config**: `pytest.ini` scopes coverage to `src/domain`, `src/application`, `src/infrastructure`, and `src/presentation/telegram/formatters.py`
- **Conventions**: Shared fixtures for domain models, mock repositories (`mock_ynab_factory`, `mock_oauth_service`, `mock_user_repository`, `mock_learning_repository`, `mock_split_config_repository`, `mock_llm_parser`, `mock_budget_query_service`), and temp files in `conftest.py`. Tests use `unittest.mock.MagicMock`. `conftest.py` adds `src/` to `sys.path`.
- **Coverage**: Run `.venv/bin/pytest` for current counts. Domain layer target: 100%.

## Key Conventions

- YNAB amounts are in milliunits (×1000), negated for expenses
- Amount formats: `40000`, `40 mil`, `40 lucas`, `40k`, `$40000`, decimals with comma (`40000,50`)
- `main.py` adds `src/` to `sys.path`, so imports within `src/` use package names directly (e.g., `from domain.models.user import ...`)
- Pre-compiled regex patterns are module-level constants (e.g., `_UUID_PATTERN`, `_SPECIAL_CHARS_PATTERN`)
- Category and account lookups use O(1) dict maps built in `_update_llm_parser_data()`
- Query matching uses a two-tier approach: LLM performs semantic matching (user term → exact YNAB name), then `BudgetQueryService` applies 4-step fuzzy matching as fallback (exact → case-insensitive → clean/no-emoji → partial)
- YNAB API responses are cached with 5-minute TTL in `YNABApiRepository`
- YNAB services use `YNABRepositoryFactory` (not a singleton repo) — always resolve per-user via `factory.get_repository(user_config)`
- SQLite migrations are versioned in `database_manager.py` `_MIGRATIONS` list (currently at v9)

## Development Workflow

Feature development follows a multi-agent pipeline. See `docs/ORCHESTRATION.md` for the full protocol and `CLAUDE.md` for agent routing. Agent definitions live in `.claude/agents/`.

