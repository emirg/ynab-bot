# Architecture

YNAB Telegram Bot — a multi-user Telegram bot that logs expenses to YNAB (You Need A Budget) using OpenAI GPT-4o-mini for natural language parsing and Whisper for voice transcription. Each user connects their own YNAB account via OAuth. Targeted at Spanish-speaking users managing budgets in Colombian pesos. All UI text and prompts are in Spanish.

Layered architecture with dependency injection and explicit runtime modes:

```
main.py → DIContainer (infrastructure/container.py)
        → AppConfig selects APP_MODE / EXTERNAL_MODE
        → public health/API server (port $PORT)
        → YNABTelegramBot only when APP_MODE=full
```

## Source Of Truth Rule

YNAB is the authoritative financial system for this project.

- The bot is an input and guidance surface, not an independent ledger.
- Users can create or modify transactions directly in YNAB web or mobile clients at any time.
- When YNAB exposes category activity, available balance, account balance, or split transaction structure, the app should prefer that data over locally inferred aggregates.
- Any disagreement between local app calculations and YNAB should be treated as a correctness bug in the app.

### Financial Read Matrix

- Spending totals, category rankings, and trend series come from YNAB transactions, with split subtransactions expanded into their real categories and bookkeeping-only zero-sum flows excluded.
- Monthly spending totals use Reflect-style net category activity from transactions:
  - negative category activity increases spending
  - real categorized inflows reduce spending
  - transfers do not count
  - `Inflow: Ready to Assign` must never offset spending
- Monthly category rankings should be built from categories whose net activity remains negative after that netting step.
- Budget-health views come from YNAB category snapshots: `budgeted`, `activity`, and especially `balance` for remaining available and overspending.
- Account balances come from YNAB account balance fields.
- Bot-local recent/edit/undo state is convenience metadata only and must not be treated as canonical financial state.

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

## Phase 3 Advisor Dashboard Baseline

The next advisor delivery keeps the same runtime and auth model, but replaces the placeholder page with the first useful read-only dashboard.

- `GET /api/v1/advisor/dashboard?period=mes|semana|dia` returns advisor-specific dashboard data for the authenticated user.
- The advisor page remains server-served HTML with lightweight inline JavaScript.
- The default advisor view is the current month.
- The first screen emphasizes overview metrics and trend analysis, with category breakdowns on the same page.
- Budget-status context is monthly and secondary, not the primary dashboard narrative.
- No frontend framework, monorepo split, or separate advisor service is introduced in this phase.

## Phase 4 Advisor Insights Baseline

The advisor keeps the same authenticated dashboard surface, but now adds deterministic interpretation on top of the existing metrics.

- `GET /api/v1/advisor/dashboard?period=mes|semana|dia` now includes additive advisor insight payloads.
- Insights remain read-only, per-user scoped, and fully deterministic.
- The first insight set covers high spending concentration, monthly pace warnings, overspent or near-limit budget categories, inactive budget categories, and an explicit all-clear fallback when no notable signal is found.
- The dashboard page renders these insights as Spanish cards inside the existing server-served HTML/JS shell.
- No LLM-generated guidance, Telegram advisor flow, configurable rule engine, frontend framework, or service split is introduced in this phase.

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
- **`src/application/services/`** — Business logic orchestrators. `ExpenseService` coordinates the full prepare→commit pipeline (parse→enhance, then create→learn) and routes between expenses and budget queries via `process_message()`. Supports confirmation mode: when enabled, `prepare_expense()` returns a preview without committing, and `commit_expense()` finalizes after user confirmation. `BudgetQueryService` handles category balance, account balance, and budget summary queries. `UserConfigService` manages per-user YNAB budget/account configuration, timezone, and confirmation mode. `YNABOAuthService` handles the full OAuth lifecycle (auth URLs, token exchange, refresh, disconnect). `LearningService` wraps the learning repository and provides dashboard/forget/stats methods. `OnboardingService` derives the user's onboarding state from existing fields (no DB column). `AdvisorAccessService` issues advisor launch URLs, exchanges launch tokens into sessions, and assembles the advisor bootstrap payload. `AdvisorDashboardService` builds advisor-specific read-only dashboard data for day/week/month periods, including KPIs, trend points, category breakdowns, month-only budget context, and deterministic advisor insights such as budget pressure, concentration, and inactive-budget signals. `SplitConfigService` manages split group configuration, person aliases, and shared account settings — validates against YNAB API before persisting. `WeeklySummaryService` fetches YNAB transactions for the past week and computes per-category spending totals. `OnDemandSummaryService` provides day/week/month spending summaries with category breakdowns.
- **`src/infrastructure/`** — Concrete implementations. `PostgresDatabaseManager` (runtime PostgreSQL connection + schema initialization), `PostgresUserRepository` (user persistence with token encryption), `PostgresLearningRepository` (per-user learning data), `PostgresSplitConfigRepository` (split groups, aliases, shared account), `PostgresAdvisorAuthRepository` (advisor launch tokens and advisor sessions), `DatabaseManager` plus the SQLite repositories (legacy compatibility and migration support only), `YNABApiRepository` (YNAB REST API), `YNABRepositoryFactory` (creates per-user YNAB repos from OAuth tokens), `TokenEncryptor` (Fernet encryption for tokens at rest), `health.py` (public HTTP server for `/`, `/oauth/callback`, `/advisor/*`, and delegated `/api/v1/*`), `TelegramNotifier` (sync HTTP wrapper for raw Telegram Bot API — used in post-OAuth callback to avoid async event loop conflicts), `scheduler.py` (weekly summary tick job, runs every 15 minutes, checks per-user timezone to fire on Monday 8am local time), `http_client.py` (resilient HTTP client with automatic retries for transient errors), and `logging_config.py` (structured logging setup). `dev/stubbed_integrations.py` provides stub parser, OAuth, and YNAB factory for local stub mode. `AppConfig` validates runtime mode and environment requirements. `DIContainer` wires everything together and swaps live vs. stub integrations.
- **`src/presentation/http/`** — Dedicated HTTP API layer. `server.py` hosts the pure router for `/api/v1/*` and `/dev/*`. In production on Railway, the public server in `health.py` delegates `/api/v1/*` to this router so health, OAuth callback, and API share the same public port. In local `http-dev`, the same router also exposes the dev harness endpoints. `handlers/expense_api_handler.py` validates auth and requests, reuses `ExpenseService` for preview/commit, and serializes JSON responses for future integrations. `handlers/advisor_api_handler.py` and `handlers/advisor_page_handler.py` enforce advisor session access for the advisor landing, bootstrap, dashboard, and logout flow. `advisor_auth.py` centralizes cookie parsing and session cookie construction. `dev_api_handler.py` powers the local `/dev/*` developer workflow.
- **`src/presentation/telegram/`** — Telegram bot and handlers. `bot.py` registers all command/message handlers and the weekly summary scheduler job. Handlers: `GeneralHandler` (includes guided onboarding via `OnboardingService`), `ConfigHandler` (includes `/connect`, `/disconnect`, `/zona` for timezone), `AdvisorHandler` (`/analisis` — issues advisor launch links for fully configured users), `ExpenseHandler` (handles text/voice/photo expenses, `/confirmacion on|off`, and confirmation callbacks), `LearningHandler` (includes `/aprendizaje`, `/olvidar`, `/deshacer`, `/editar`), `SplitConfigHandler` (`/splitwise` — split group CRUD, alias management, shared account config via inline keyboards with pagination), `SummaryHandler` (`/resumen` — on-demand spending summary), `AdminHandler`. `keyboards.py` provides shared inline keyboard builders (confirmation keyboard, budget/account selection, split config panels with pagination). Auth via `@require_authentication` and `@require_admin` decorators.

## Supporting Modules

- **`src/parsers/llm_expense_parser.py`** — `LLMExpenseParser` (GPT-4o-mini), used by `ExpenseService` via DI. `parse_message()` classifies intent (`expense` | `query` | `shared_expense`) in a single LLM call; the LLM performs semantic matching to map user terms (e.g., "comida") to exact YNAB category names (e.g., "🛒 Groceries") using up to 100 categories in the prompt. Also extracts optional `date` field (relative or absolute, resolved to `YYYY-MM-DD`) and shared expense fields (`person`, `proportion`, `payer`, `user_share_amount`, `other_share_amount`; legacy `split_amount` remains accepted). `parse_receipt_image()` handles vision-based receipt extraction using the same JSON output format. `parse_expense()` is retained for backward compatibility (voice handler).
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
      → normalize responsibility into user_share and other_share
      → if payer == "user" and both shares are positive: subtransactions (real category + split tracking category)
      → if payer == "user" and one share is zero: regular one-category transaction
      → if payer == "other" and user_share is positive: zero-sum transaction (outflow + inflow balance to $0)
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

Split expenses use YNAB subtransactions or regular one-category transactions to track debts via a dedicated Splitwise tracking category. The internal contract separates payer from responsibility: `payer` decides the account flow, while normalized `user_share` and `other_share` decide the category shape.

- **User-paid split**: Transaction with two subtransactions — user's share goes to the real category, the other person's share goes to the split tracking category.
- **User-paid 100% other responsibility**: Regular transaction categorized only to the split tracking category. This avoids zero-amount real-category split legs.
- **User-paid 100% user responsibility**: Regular transaction categorized only to the real category. This avoids zero-amount split tracking legs.
- **Third-party paid split** (zero-sum): Transaction amount is `$0` with two subtransactions — outflow from real category balanced by inflow to split tracking category. Uses the shared tracking account configured via `/splitwise`.
- **Third-party paid inference**: When a configured split person is the subject of "gastó", "pagó", or "compró", the parser treats the message as a shared expense involving the user. Without an explicit share, it defaults to 50/50; "me compró", "por mí", and "para mí" make the user's share 100%.
- **Third-party paid zero user responsibility**: No YNAB transaction is created because there is no user expense or debt to register.
- **Fixed shares**: Parser output can identify either `user_share_amount` (e.g., "70k son míos") or `other_share_amount` (e.g., "70k son de Eli"). Conflicting explicit shares are rejected before YNAB creation.
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

Hosted on Railway. CI pipeline runs the executable harness and tests on build — if either fails, deploy is cancelled.

```toml
# railway.toml
[build]
buildCommand = "pip install -r requirements.txt && python scripts/harness/verify.py --ci && pytest"
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
- `GET /api/v1/advisor/dashboard?period=mes|semana|dia`
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
