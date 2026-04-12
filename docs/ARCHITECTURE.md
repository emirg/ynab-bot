# Architecture

YNAB Telegram Bot — a multi-user Telegram bot that logs expenses to YNAB (You Need A Budget) using OpenAI GPT-4o-mini for natural language parsing and Whisper for voice transcription. Each user connects their own YNAB account via OAuth. Targeted at Spanish-speaking users managing budgets in Colombian pesos. All UI text and prompts are in Spanish.

Layered architecture with dependency injection and explicit runtime modes:

```
main.py → DIContainer (infrastructure/container.py)
        → AppConfig selects APP_MODE / EXTERNAL_MODE
        → public health/API server (port $PORT)
        → YNABTelegramBot only when APP_MODE=full
```

## Phase 1 Advisor Baseline

Financial Advisor Phase 1 starts from the current shipped runtime, not from an assumed future repo split or mandatory multi-service topology.

- The current repository is the implementation unit.
- The current public HTTP server remains the public entrypoint during Phase 1.
- Railway should continue running `APP_MODE=full`.
- Local advisor-related development should continue using the existing HTTP-first `http-dev` workflow.
- Telegram and HTTP continue sharing the current service boundaries until a later ADR explicitly changes that architecture.

## Phase 2 Advisor Access Baseline

The first advisor delivery continues on the same public HTTP server and uses Telegram as the only entrypoint.

- `/analisis` issues a short-lived one-time advisor launch link.
- `GET /advisor/launch` exchanges that link for a server-side advisor session.
- The browser receives an HTTP-only `advisor_session` cookie.
- `GET /advisor` serves the authenticated landing page.
- `GET /api/v1/advisor/bootstrap` and `POST /api/v1/advisor/logout` are session-authenticated advisor routes.
- Advisor launch tokens and sessions are stored hashed at rest in PostgreSQL.

## Runtime Modes

- **`APP_MODE=full`** — production-style runtime. Starts the public HTTP server and Telegram polling.
- **`APP_MODE=http-dev`** — default local development runtime. Starts the public HTTP server, enables `/dev/*`, disables Telegram polling, and normally uses stubbed integrations.
- **`APP_MODE=http-live`** — HTTP-only runtime with live OpenAI and YNAB integrations, but no Telegram polling.
- **`APP_MODE=test`** — test-oriented runtime.

Integration behavior is controlled separately by `EXTERNAL_MODE`:

- **`EXTERNAL_MODE=live`** — real OpenAI, YNAB OAuth, YNAB API, and speech integrations.
- **`EXTERNAL_MODE=stub`** — stubbed parser, OAuth service, and YNAB repository factory for fast local development.

## Layers

- **`src/domain/`** — Domain models (`Expense`, `UserConfiguration`, `YNABCategory`, `YNABAccount`, `YNABBudget`, `BudgetQueryResult`, `MessageResult`, `OnboardingStep`, `SplitGroup`, `SharedAccountConfig`, `WeeklySummary`, `OnDemandSummary`), repository interfaces (abstract base classes), `AuthorizationService`, `payee_normalizer`, `time_utils` (timezone-aware date helpers), and custom exceptions. No external dependencies.
- **`src/application/services/`** — Business logic orchestrators. `ExpenseService` coordinates the full prepare→commit pipeline (parse→enhance, then create→learn) and routes between expenses and budget queries via `process_message()`. Supports confirmation mode: when enabled, `prepare_expense()` returns a preview without committing, and `commit_expense()` finalizes after user confirmation. `BudgetQueryService` handles category balance, account balance, and budget summary queries. `UserConfigService` manages per-user YNAB budget/account configuration, timezone, and confirmation mode. `YNABOAuthService` handles the full OAuth lifecycle (auth URLs, token exchange, refresh, disconnect). `LearningService` wraps the learning repository and provides dashboard/forget/stats methods. `OnboardingService` derives the user's onboarding state from existing fields (no DB column). `AdvisorAccessService` issues advisor launch URLs, exchanges launch tokens into sessions, and assembles the advisor bootstrap payload. `SplitConfigService` manages split group configuration, person aliases, and shared account settings — validates against YNAB API before persisting. `WeeklySummaryService` fetches YNAB transactions for the past week and computes per-category spending totals. `OnDemandSummaryService` provides day/week/month spending summaries with category breakdowns.
- **`src/infrastructure/`** — Concrete implementations. `PostgresDatabaseManager` (runtime PostgreSQL connection + schema initialization), `PostgresUserRepository` (user persistence with token encryption), `PostgresLearningRepository` (per-user learning data), `PostgresSplitConfigRepository` (split groups, aliases, shared account), `PostgresAdvisorAuthRepository` (advisor launch tokens and advisor sessions), `DatabaseManager` plus the SQLite repositories (legacy compatibility and migration support only), `YNABApiRepository` (YNAB REST API), `YNABRepositoryFactory` (creates per-user YNAB repos from OAuth tokens), `TokenEncryptor` (Fernet encryption for tokens at rest), `health.py` (public HTTP server for `/`, `/oauth/callback`, `/advisor/*`, and delegated `/api/v1/*`), `TelegramNotifier` (sync HTTP wrapper for raw Telegram Bot API — used in post-OAuth callback to avoid async event loop conflicts), `scheduler.py` (weekly summary tick job, runs every 15 minutes, checks per-user timezone to fire on Monday 8am local time), `http_client.py` (resilient HTTP client with automatic retries for transient errors), and `logging_config.py` (structured logging setup). `dev/stubbed_integrations.py` provides stub parser, OAuth, and YNAB factory for local stub mode. `AppConfig` validates runtime mode and environment requirements. `DIContainer` wires everything together and swaps live vs. stub integrations.
- **`src/presentation/http/`** — Dedicated HTTP API layer. `server.py` hosts the pure router for `/api/v1/*` and `/dev/*`. In production on Railway, the public server in `health.py` delegates `/api/v1/*` to this router so health, OAuth callback, and API share the same public port. In local `http-dev`, the same router also exposes the dev harness endpoints. `handlers/expense_api_handler.py` validates auth and requests, reuses `ExpenseService` for preview/commit, and serializes JSON responses for future integrations. `handlers/advisor_api_handler.py` and `handlers/advisor_page_handler.py` enforce advisor session access for the new landing/bootstrap/logout flow. `advisor_auth.py` centralizes cookie parsing and session cookie construction. `dev_api_handler.py` powers the local `/dev/*` developer workflow.
- **`src/presentation/telegram/`** — Telegram bot and handlers. `bot.py` registers all command/message handlers and the weekly summary scheduler job. Handlers: `GeneralHandler` (includes guided onboarding via `OnboardingService`), `ConfigHandler` (includes `/connect`, `/disconnect`, `/zona` for timezone), `AdvisorHandler` (`/analisis` — issues advisor launch links for fully configured users), `ExpenseHandler` (handles text/voice/photo expenses, `/confirmacion on|off`, and confirmation callbacks), `LearningHandler` (includes `/aprendizaje`, `/olvidar`, `/deshacer`, `/editar`), `SplitConfigHandler` (`/splitwise` — split group CRUD, alias management, shared account config via inline keyboards with pagination), `SummaryHandler` (`/resumen` — on-demand spending summary), `AdminHandler`. `keyboards.py` provides shared inline keyboard builders (confirmation keyboard, budget/account selection, split config panels with pagination). Auth via `@require_authentication` and `@require_admin` decorators.

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

HTTP client → public server in `infrastructure/health.py`
  → `/api/v1/*` delegated to `presentation/http/server.py`
  → `/dev/*` delegated to `presentation/http/dev_api_handler.py` only in `http-dev`
```

## Per-User YNAB OAuth

Each user connects their own YNAB account. No shared global token.

```
User → /connect → generate OAuth URL with HMAC-signed state
     → YNAB authorization page → redirect to /oauth/callback
     → exchange code for tokens → encrypt & store in PostgreSQL
     → YNABRepositoryFactory creates per-user YNABApiRepository on each request
```

- **Token lifecycle**: auto-refresh when expired (5-min buffer), Fernet-encrypted at rest in PostgreSQL
- **State security**: HMAC-SHA256 signed with `YNAB_CLIENT_SECRET` to prevent CSRF
- **OAuth callback**: served by the health check HTTP server at `/oauth/callback`

## Shared Expenses

Split expenses use YNAB subtransactions to track debts via a dedicated Splitwise tracking category.

- **User-paid split**: Transaction with two subtransactions — user's share goes to the real category, the other person's share goes to the split tracking category.
- **Third-party paid split** (zero-sum): Transaction amount is `$0` with two subtransactions — outflow from real category balanced by inflow to split tracking category. Uses the shared tracking account configured via `/splitwise`.
- **100% debt**: When `proportion=1` and `payer=other`, user owes the full amount (e.g., "Juan pagó el mercado por mí").
- **Configuration**: `SplitConfigService` manages split groups (linked to YNAB categories), person aliases, and shared account — validates against YNAB API before persisting. Runtime data lives in the PostgreSQL `split_groups`, `split_person_aliases`, and `split_shared_account` tables.

## User Authentication

Multi-user system with admin approval. Users have statuses: `PENDING` → `AUTHORIZED` or `BLOCKED`. Admins are configured via `ADMIN_IDS` env var (required). Admin commands: `/admin`, `/pending`, `/users`, `/approve`, `/block`.

## Configuration

Environment variables are validated by `AppConfig` and loaded from the chosen env file:

- `config/.env` for production-style or full-mode runs
- `config/.env.dev` for local `http-dev` and `http-live` workflows

Core settings:
- `APP_MODE` (`full`, `http-dev`, `http-live`, `test`)
- `EXTERNAL_MODE` (`live`, `stub`)
- `TOKEN_ENCRYPTION_KEY`
- `HTTP_API_KEY`
- `ADMIN_IDS`
- `POSTGRES_DSN`

Required only when the selected runtime needs them:
- `TELEGRAM_BOT_TOKEN` when Telegram polling is enabled
- `OPENAI_API_KEY`, `YNAB_CLIENT_ID`, `YNAB_CLIENT_SECRET`, `YNAB_REDIRECT_URI` when `EXTERNAL_MODE=live`
- `DEV_API_KEY` when `APP_MODE=http-dev`
- `ENABLE_DEV_ROUTES=true` only with `APP_MODE=http-dev`

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

Public HTTP server runs on `$PORT` (default 8080), serves `/` for Railway health checks, `/oauth/callback` for YNAB OAuth, and `POST /api/v1/expenses/text` for the authenticated expense API.

Advisor access now also lives on the same public server:
- `GET /advisor/launch`
- `GET /advisor`
- `GET /api/v1/advisor/bootstrap`
- `POST /api/v1/advisor/logout`

Railway should run the production runtime (`APP_MODE=full`). Local Docker profiles (`app-dev`, `app-live`, optional `postgres`) are development-only and should not be confused with the deployed topology.

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
- PostgreSQL schema initialization is managed by `postgres_schema.py` through `PostgresDatabaseManager`; the older SQLite migration list remains only as a compatibility baseline for one-time migration tooling.

## Development Workflow

Feature development follows a staged documentation and execution workflow:

- `docs/DOCUMENTATION_WORKFLOW.md` defines the `SPEC -> PLAN -> IMPLEMENT -> ADR` lifecycle
- `docs/AI_WORKFLOW.md` defines how approved work is executed, reviewed, and handed off

Local day-to-day development is HTTP-first:

1. Start `docker compose up app-dev`
2. Bootstrap a local user through `scripts/dev/bootstrap_user.py`
3. Exercise flows through `/dev/*`, `scripts/dev/send_message.py`, or the Postman bundle in `docs/dev/postman/`
4. Run tests with `.venv/bin/pytest`

AI-specific routing remains in `CLAUDE.md`, `GEMINI.md`, and `AGENTS.md`.
