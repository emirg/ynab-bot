# 🤖 YNAB Telegram Bot

A multi-user Telegram bot that logs expenses to YNAB (You Need A Budget) using OpenAI for natural language parsing and Whisper for voice transcription. Targeted at Spanish-speaking users managing budgets in Colombian pesos.

## Source Of Truth

YNAB is the source of truth for the product.

- Users may register expenses through the bot, but they may also create, edit, split, move, or reconcile transactions directly in YNAB.
- Any spending view, budget status, category total, or advisor signal must prefer YNAB data over locally inferred state whenever YNAB provides the relevant information.
- Local bot state exists to help capture and route data, not to compete with or override YNAB's financial reality.

This rule matters for users, developers, and AI assistants working on the codebase.

### Financial Read Matrix

- Spending totals, category rankings, and spend trends use YNAB transactions with split subtransactions expanded and non-spending bookkeeping ignored.
- Monthly `Total gastado` follows Reflect-style net category activity: negative category activity increases spending, real categorized inflows can offset it, transfers are ignored, and `Inflow: Ready to Assign` does not reduce spending.
- Monthly top categories come from negative-net category activity after that netting step; positive-only reimbursement categories should not appear as spending leaders.
- Budget status, category availability, overspending, and monthly activity use YNAB category snapshot fields `budgeted`, `activity`, and `balance`.
- Account balances use YNAB account balance fields directly.
- `/recent`, `/editar`, and `/deshacer` are workflow conveniences backed by recent bot references, not canonical financial reporting.

## ✨ Features

- 🎤 **Voice Recognition**: Send audio messages and the bot transcribes them automatically with Whisper
- 📸 **Receipt Scanning**: Send a photo of a receipt and the bot extracts amount, merchant, and category automatically
- 🧠 **AI-Powered**: Uses OpenAI structured parsing to understand expenses and budget queries in natural Spanish language
- 📊 **Budget Queries**: Ask about category balances, account balances, or get a budget summary in natural language
- 📅 **Date Parsing**: Supports relative ("ayer", "el lunes") and absolute ("24/07", "el 5 de marzo") dates for backdating expenses
- 👥 **Shared Expenses**: Split expenses with other people — separates who paid from who owes, including 50/50, fixed-share, 100% debt, and third-party paid scenarios
- 📚 **Adaptive Learning**: Remembers your spending patterns, explains categorization decisions, and improves over time
- 💳 **Account Detection**: Automatically identifies the bank account mentioned
- 🏪 **Smart Categorization**: Assigns real YNAB categories based on merchant/location with semantic matching
- 👥 **Multi-User**: Authentication system with admin approval and guided onboarding
- 🔐 **Per-User OAuth**: Each user connects their own YNAB account via OAuth2
- ✏️ **Edit & Undo**: Edit recent transactions (amount, payee, category, account) or undo the last one entirely
- ✅ **Confirmation Mode**: Optional pre-registration preview — the bot shows what it will log and waits for confirmation
- 📊 **Weekly & On-Demand Summaries**: Automatic weekly spending summary every Monday + on-demand summary via `/resumen`
- 🕐 **Timezone Support**: Per-user timezone configuration for accurate date handling and weekly summaries
- 📊 **Statistics**: View learning progress, top payees/categories, and accuracy improvements

## 📁 Project Structure

```
ynab-bot/
├── main.py                          # Entry point
├── requirements.txt                 # Python dependencies
├── pytest.ini                       # Test configuration
├── docker-compose.yml               # Local dev profiles (http-dev, http-live, postgres)
├── railway.toml                     # Railway build/deploy config
├── src/
│   ├── domain/                      # Models, interfaces, exceptions
│   │   ├── models/                  # Expense, summaries, onboarding, split config
│   │   ├── repositories/            # Abstract interfaces (ABC)
│   │   ├── services/                # AuthorizationService, payee_normalizer
│   │   ├── time_utils.py            # Timezone-aware date helpers
│   │   └── exceptions.py            # Domain and configuration exceptions
│   ├── application/services/        # Business logic orchestrators
│   │   ├── expense_service.py       # Parse/prepare/commit flow + query routing + shared expenses
│   │   ├── budget_query_service.py  # Category/account/budget summary queries
│   │   ├── user_config_service.py   # Budget, account, timezone, confirmation config
│   │   ├── oauth_service.py         # YNAB OAuth2 lifecycle (auth, refresh, disconnect)
│   │   ├── learning_service.py      # Dashboard, forget, stats
│   │   ├── onboarding_service.py    # Guided onboarding state derivation
│   │   ├── split_config_service.py  # Split group, alias, shared account management
│   │   ├── weekly_summary_service.py # Automated weekly spending summary
│   │   └── on_demand_summary_service.py # On-demand spending summary
│   ├── infrastructure/
│   │   ├── config/app_config.py     # Runtime mode and env validation
│   │   ├── container.py             # Dependency injection (DIContainer)
│   │   ├── health.py                # Public HTTP server: /, /oauth/callback, /api/v1/*
│   │   ├── scheduler.py             # Weekly summary scheduler
│   │   ├── http_client.py           # Resilient HTTP client with retries
│   │   ├── logging_config.py        # Structured logging setup
│   │   ├── token_encryption.py      # Fernet encryption for tokens at rest
│   │   ├── telegram_notifier.py     # Sync Telegram API wrapper (post-OAuth notifications)
│   │   ├── dev/                     # Stubbed integrations for local http-dev
│   │   └── repositories/            # Postgres runtime repos, SQLite migration support, YNAB API, repo factory
│   ├── presentation/http/
│   │   ├── server.py                # Pure router for /api/v1/* and /dev/*
│   │   ├── auth.py                  # Bearer auth validation
│   │   ├── dev_api_handler.py       # Local dev harness endpoints
│   │   ├── serializers.py           # JSON response serialization
│   │   └── handlers/
│   │       └── expense_api_handler.py # POST /api/v1/expenses/text
│   ├── presentation/telegram/
│   │   ├── bot.py                   # Handler registration
│   │   ├── formatters.py            # Message formatting (expenses, queries, summaries)
│   │   ├── keyboards.py             # Inline keyboard builders
│   │   ├── handlers/                # General, Config, Expense, Learning, SplitConfig, Summary, Admin
│   │   └── middleware/              # @require_authentication, @require_admin
│   ├── parsers/
│   │   └── llm_expense_parser.py    # GPT-based parser for text and receipts
│   └── integrations/
│       └── speech_to_text.py        # Whisper transcription
├── config/
│   ├── .env.example                 # Production/full-mode template
│   ├── .env.dev.example             # Local http-dev/http-live template
│   └── .env*                        # Local private env files (not committed)
├── data/                            # Persistent data
│   └── *.db                         # Legacy SQLite files used only for migration/compatibility tooling
├── scripts/
│   └── dev/                         # Local bootstrap/send-message helpers
├── docs/
│   ├── dev/                         # Local DX, harness, and Postman guides
│   ├── specs/                       # Feature specifications
│   ├── plans/                       # Implementation plans
│   └── adrs/                        # Architecture decision records
└── tests/                           # Pytest suite
```

## 🚀 Setup & Local Development

The detailed setup and local development guide now lives in [docs/dev/README.md](docs/dev/README.md).

Use that guide for:

- first-time project bootstrap
- local `http-dev` workflow
- environment configuration
- Docker profiles and PostgreSQL setup
- dev harness scripts and Postman usage

Minimal bootstrap:

```bash
git clone <repository-url>
cd ynab-bot
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

After the environment exists, prefer project commands through `.venv/bin/...` such as `.venv/bin/python main.py` and `.venv/bin/pytest`.

## HTTP API

The service exposes an authenticated HTTP endpoint on the same public port/domain used by Railway health checks and the YNAB OAuth callback.

### `POST /api/v1/expenses/text`

Headers:

```http
Authorization: Bearer <HTTP_API_KEY>
Content-Type: application/json
```

Body:

```json
{
  "telegram_user_id": 7321506689,
  "text": "Gaste 25k en Carulla",
  "force_commit": false
}
```

Behavior:
- If the user has `confirm_before_create=true` and `force_commit` is absent or `false`, the endpoint returns `status=preview` and does not create the transaction.
- Otherwise it commits immediately and returns `status=committed`.
- `query` intents are rejected with `422`.

Example:

```bash
curl -X POST "https://<your-railway-domain>/api/v1/expenses/text" \
  -H "Authorization: Bearer <HTTP_API_KEY>" \
  -H "Content-Type: application/json" \
  -d '{
    "telegram_user_id": 7321506689,
    "text": "Gaste 25k en Carulla"
  }'
```

## 📱 Usage

### Available Commands

**General:**
- `/start` — Registration and welcome message
- `/help` — Help and usage examples

**YNAB Connection:**
- `/connect` — Connect your YNAB account via OAuth
- `/disconnect` — Disconnect your YNAB account and clear tokens

**Configuration:**
- `/config` — Configure YNAB budget and accounts
- `/budgets` — List available budgets
- `/accounts` — List available accounts
- `/status` — View current configuration and YNAB connection status
- `/zona <timezone>` — Configure timezone (e.g. `/zona America/Bogota`)
- `/confirmacion on|off` — Enable/disable confirmation before registering expenses

**Shared Expenses:**
- `/splitwise` — Configure Splitwise groups, person aliases, and shared account

**Learning & Transactions:**
- `/stats` — Learning statistics (top payees and categories)
- `/aprendizaje` — View learned payee-category associations with frequency
- `/olvidar <payee>` — Delete incorrect associations for a payee
- `/recent` — View recent transactions
- `/editar [n] <campo> <valor>` — Edit a recent transaction (amount, payee, category, account). Optional index `n` (default: last).
- `/deshacer` — Undo the last transaction (deletes from YNAB, decrements learning)

**Summaries:**
- `/resumen` — On-demand spending summary (day/week/month with category breakdown)

**Administration** (admins only):
- `/admin` — Admin panel
- `/pending` — View users pending approval
- `/users` — View all users
- `/approve <user_id>` — Approve a user
- `/block <user_id>` — Block a user

### Supported Message Formats

The bot understands various natural language formats for logging expenses in Spanish:

```
"Gasté $50000 en comida en Éxito"
"Me gasté 25000 pesos en transporte"
"$30000 comida Carulla"
"45000 pesos gasolina con mi tarjeta Nu"
"25 lucas almuerzo McDonald's"
"80k gasolina estación Terpel"
"Almuerzo 25000 en Home Burguer"
"Ayer gasté 30k en restaurante"
"El lunes pagué 15000 en farmacia"
```

Amount formats: `40000`, `40 mil`, `40 lucas`, `40k`, `$40000`, decimals with comma (`40000,50`).

Date formats: `ayer`, `anteayer`, `el lunes`, `la semana pasada`, `24/07`, `el 5 de marzo`. If no date is mentioned, today is assumed.

### Shared Expenses

The bot supports shared expenses by separating the payer from the person responsible for the cost:

```
"Almuerzo compartido con Juan 30k"           → 50/50 split, user paid
"Cena con María 60k, ella pagó"              → 50/50 split, third-party paid
"Frank gastó 71800 en Pret"                    → 50/50 split, third-party paid
"Juan pagó 100k de mercado por mí"           → 100% debt, third-party paid
"Frank me compró algo en Farmatodo por 14200"  → 100% debt, third-party paid
"Compré una hamburguesa para Juan 100k"      → 100% debt, user paid
```

**User-paid split**: Creates subtransactions splitting the amount between the real category and the Splitwise tracking category.

**User-paid 100% other responsibility**: Creates one regular transaction in the Splitwise tracking category. It does not create a split with a zero real-category leg.

**Third-party paid split**: Creates a zero-sum transaction — the real category outflow is balanced by an inflow from the Splitwise tracking category, so your budget reflects the debt without affecting your account balance.

When a configured split person is the subject of "gastó", "pagó", or "compró", the parser assumes the message is registering a shared expense involving the user. The user does not need to write "conmigo" for the default 50/50 case.

Configure split groups, person aliases, and tracking accounts via `/splitwise`.

### Budget Queries

Ask about your budget in natural language:

```
"¿Cuánto me queda en comida?"           → Category balance (matches "🛒 Groceries" semantically)
"¿Cuánto debo en mi Nu Card?"           → Account balance (confirmed/pending)
"¿Cómo va mi presupuesto?"              → Budget summary with top spending categories
"¿Cuánto he gastado en restaurantes?"    → Category balance (matches "🍽️ Dining Out" or similar)
"¿Cuál es el saldo de mi cuenta?"       → Account balance
```

The bot uses AI-powered semantic matching to map natural language terms to your actual YNAB categories — you don't need to remember exact category names. It distinguishes between expenses and queries automatically.

### Receipt Photos

Send a photo of a receipt or ticket and the bot will:
1. Analyze the image using OpenAI GPT-4o-mini vision
2. Extract the total amount, merchant, and individual items (for memo)
3. Log it to YNAB automatically

You can add a caption to the photo for additional context (e.g., "lunch with friends").

### Voice Messages

Send a voice message in Spanish and the bot will:
1. Transcribe the audio using OpenAI Whisper
2. Parse the expense information
3. Log it to YNAB automatically

### Account Detection

The bot detects bank accounts mentioned in messages:
- "con mi tarjeta Nu" → Nu Card account
- "con Rappi Card" → Rappi Card account
- "efectivo" → Cash account

### Edit & Undo

- Use `/editar categoria <nueva categoría>` to correct the last transaction's category (the bot learns from the correction)
- Use `/editar monto <nuevo monto>` to fix the amount
- Use `/editar 2 categoria Restaurantes` to edit the second-to-last transaction
- Use `/deshacer` to delete the last transaction entirely (also reverts learning)

## 👥 Authentication & YNAB Connection

The bot implements a multi-user system with admin approval and per-user OAuth:

1. A new user sends `/start` → status set to **PENDING**
2. All other commands are blocked until approved
3. An admin reviews the request with `/pending` and approves or blocks
4. The user receives a notification and can start using the bot
5. User connects their own YNAB account via `/connect` (OAuth2 Authorization Code flow)
6. After OAuth, configures their budget (`/budgets`) and account (`/accounts`)

User statuses: `PENDING` → `AUTHORIZED` | `BLOCKED`

### OAuth2 Flow

Each user connects their own YNAB account. No shared tokens.

1. User sends `/connect` → bot generates an authorization URL with HMAC-SHA256 signed state
2. User clicks the link → authorizes the app on YNAB's site
3. YNAB redirects to the bot's callback endpoint (`/oauth/callback`) with an authorization code
4. Bot exchanges the code for access + refresh tokens, encrypts them with Fernet, and stores in PostgreSQL
5. Tokens are automatically refreshed when expired

**Security:**
- OAuth state parameter signed with HMAC-SHA256 (using `YNAB_CLIENT_SECRET`) to prevent CSRF
- Tokens encrypted at rest with Fernet symmetric encryption (`TOKEN_ENCRYPTION_KEY`)
- Tokens are never logged

## 🧪 Tests

```bash
# Full suite
.venv/bin/pytest

# Single test file
.venv/bin/pytest tests/test_domain_models.py

# Single test class or method
.venv/bin/pytest tests/test_domain_models.py::TestExpense::test_is_valid_basic

# Filter by name
.venv/bin/pytest -k "test_predict_category"
```

## 🏗️ Architecture

Layered architecture with dependency injection and explicit runtime modes:

```
main.py → DIContainer (infrastructure/container.py)
        → AppConfig selects APP_MODE / EXTERNAL_MODE
        → public HTTP server on $PORT (health + OAuth + HTTP API)
        → Telegram polling only when APP_MODE=full
```

Runtime summary:
- `full`: Railway/production runtime, public HTTP server plus Telegram polling
- `http-dev`: local DX runtime, public HTTP server plus `/dev/*`, no Telegram polling
- `http-live`: HTTP-only runtime with live OpenAI/YNAB integrations
- `test`: test-oriented runtime

**Message and HTTP processing flow:**
```
User (text)
  → ExpenseService.process_message()
    → LLMExpenseParser.parse_message() → classifies intent ("expense" | "query" | "shared_expense")
    → LLM semantically maps user terms to exact YNAB category/account names
    → if expense: prepare pipeline (parse→enhance) → confirm or auto-commit → create→learn
    → if shared_expense: split logic (subtransactions or zero-sum) → create→learn
    → if query: BudgetQueryService (4-step fuzzy fallback) → category/account/summary data
  → Formatted Telegram response

User (voice)
  → Whisper transcription
  → ExpenseService.process_expense_message() → expense pipeline

User (photo)
  → GPT-4o-mini vision (receipt extraction)
  → ExpenseService.process_receipt_image() → expense pipeline

HTTP client
  → public server in infrastructure/health.py
    → /api/v1/* delegated to presentation/http/server.py
    → /dev/* delegated to presentation/http/dev_api_handler.py in http-dev only
```

The public HTTP surface is shared:
- `/` for Railway health checks
- `/oauth/callback` for YNAB OAuth
- `/api/v1/expenses/text` for the authenticated expense API
- `/dev/*` only in local `http-dev`

## 🚀 Deployment

The bot is configured for deployment on **Railway** with:

- **Production runtime**: Railway should run `APP_MODE=full`, which enables Telegram polling and the public HTTP server
- **Test-gating**: Tests run before every deploy; failures cancel the deployment (`railway.toml`)
- **Health check**: Built-in HTTP server at `/` for Railway health probes
- **OAuth callback**: Same public HTTP server handles `/oauth/callback` for the YNAB OAuth flow
- **Authenticated API**: Same public HTTP server also exposes `POST /api/v1/expenses/text`
- **Guardrails**: `APP_MODE=http-dev` is blocked on Railway by startup validation

To use the HTTP endpoint after deploy, set `HTTP_API_KEY` in Railway and call the same service domain at `/api/v1/expenses/text`.

Local Docker profiles are for development only:
- `docker compose up app-dev` for stubbed local HTTP-first development
- `docker compose --profile live-integrations up app-live` for local HTTP-only runs with real OpenAI/YNAB integrations
- `docker compose --profile postgres up postgres` only when you need a local Postgres instance for migration or integration work

### YNAB OAuth App Setup

1. Go to [YNAB Developer Settings](https://app.ynab.com/settings/developer)
2. Create a new OAuth Application
3. Set the Redirect URI to `https://<your-railway-domain>/oauth/callback`
4. Copy the Client ID and Client Secret to your environment variables

## 🛠️ Development Workflow

Feature work is documented and executed in stages:

- `SPEC` in `docs/specs/` defines what to build
- `PLAN` in `docs/plans/` defines how to build it
- `ADR` in `docs/adrs/` records significant architectural decisions

Practical local workflow:

1. Start the default local profile with `docker compose up app-dev`
2. Bootstrap a local user with `.venv/bin/python scripts/dev/bootstrap_user.py --dev-api-key "$DEV_API_KEY"`
3. Exercise flows through `.venv/bin/python scripts/dev/send_message.py ...` or the Postman collection in `docs/dev/postman/`
4. Run tests with `.venv/bin/pytest`

Documentation references:
- [docs/DOCUMENTATION_WORKFLOW.md](docs/DOCUMENTATION_WORKFLOW.md) defines when SPECs, PLANs, and ADRs are required
- [docs/AI_WORKFLOW.md](docs/AI_WORKFLOW.md) defines the execution and handoff pipeline
- [docs/dev/README.md](docs/dev/README.md) documents the current HTTP-first local DX
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) describes the runtime architecture in more detail
