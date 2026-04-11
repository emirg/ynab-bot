# 🤖 YNAB Telegram Bot

A multi-user Telegram bot that logs expenses to YNAB (You Need A Budget) using OpenAI GPT-4o-mini for natural language parsing and Whisper for voice transcription. Targeted at Spanish-speaking users managing budgets in Colombian pesos.

## ✨ Features

- 🎤 **Voice Recognition**: Send audio messages and the bot transcribes them automatically with Whisper
- 📸 **Receipt Scanning**: Send a photo of a receipt and the bot extracts amount, merchant, and category automatically
- 🧠 **AI-Powered**: Uses OpenAI GPT-4o-mini to understand expenses and budget queries in natural Spanish language
- 📊 **Budget Queries**: Ask about category balances, account balances, or get a budget summary in natural language
- 📅 **Date Parsing**: Supports relative ("ayer", "el lunes") and absolute ("24/07", "el 5 de marzo") dates for backdating expenses
- 👥 **Shared Expenses**: Split expenses with other people — supports user-paid and third-party paid scenarios with automatic YNAB subtransactions
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
├── railway.toml                     # Railway deployment config (test-gating)
├── src/
│   ├── domain/                      # Models, interfaces, exceptions
│   │   ├── models/                  # Expense, BudgetQueryResult, UserConfiguration, SplitGroup, OnboardingStep
│   │   ├── repositories/           # Abstract interfaces (ABC)
│   │   ├── services/               # AuthorizationService, payee_normalizer
│   │   └── exceptions.py           # Includes OAuthException, TokenExpiredException
│   ├── application/services/        # Business logic orchestrators
│   │   ├── expense_service.py       # Pipeline: parse→enhance→create→learn + query routing + shared expenses
│   │   ├── budget_query_service.py  # Budget queries (category/account balance, summary)
│   │   ├── user_config_service.py   # Per-user configuration
│   │   ├── oauth_service.py         # YNAB OAuth2 lifecycle (auth, tokens, refresh)
│   │   ├── learning_service.py      # Dashboard, forget, stats
│   │   ├── onboarding_service.py    # Guided onboarding state derivation
│   │   ├── split_config_service.py  # Split group/alias/shared account management
│   │   ├── weekly_summary_service.py # Automated weekly spending summary
│   │   └── on_demand_summary_service.py # On-demand spending summary
│   ├── infrastructure/
│   │   ├── config/app_config.py     # Loads config/.env
│   │   ├── container.py             # Dependency injection (DIContainer)
│   │   ├── health.py                # Public HTTP server: health + OAuth callback + /api/v1/*
│   │   ├── scheduler.py             # Weekly summary job scheduler
│   │   ├── http_client.py           # Resilient HTTP client with retries
│   │   ├── logging_config.py        # Structured logging setup
│   │   ├── token_encryption.py      # Fernet encryption for tokens at rest
│   │   ├── telegram_notifier.py     # Sync Telegram API wrapper (post-OAuth notifications)
│   │   └── repositories/           # SQLite, YNAB API, YNABRepositoryFactory
│   ├── presentation/http/
│   │   ├── server.py                # Pure router + optional standalone HTTP transport
│   │   ├── auth.py                  # Bearer auth validation
│   │   ├── serializers.py           # JSON response serialization
│   │   └── handlers/
│   │       └── expense_api_handler.py # POST /api/v1/expenses/text
│   ├── presentation/telegram/
│   │   ├── bot.py                   # Handler registration
│   │   ├── formatters.py           # Message formatting (expenses, queries, shared)
│   │   ├── keyboards.py            # Inline keyboard builders (budgets, accounts, split config)
│   │   ├── handlers/               # General, Config, Expense, Learning, SplitConfig, Summary, Admin
│   │   └── middleware/             # @require_authentication, @require_admin
│   ├── parsers/
│   │   └── llm_expense_parser.py    # GPT-4o-mini parser (intent classification, date parsing, shared expenses)
│   └── integrations/
│       └── speech_to_text.py        # Whisper transcription
├── config/
│   ├── .env                         # Environment variables (private)
│   └── .env.example                 # Configuration template
├── data/                            # Persistent data
│   └── users.db                     # SQLite database (users, learning, split config)
└── tests/                           # Test suite
```

## 🚀 Installation & Setup

### 1. Clone the repository
```bash
git clone <repository-url>
cd ynab-bot
```

### 2. Create virtual environment and install dependencies
```bash
python -m venv .venv
source .venv/bin/activate  # or: source .venv/bin/activate.fish
pip install -r requirements.txt
```

### 3. Configure environment variables
```bash
cp config/.env.example config/.env
```

Edit `config/.env` with your tokens:

| Variable | Description | Required |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | Telegram bot token (via [@BotFather](https://t.me/botfather)) | Yes |
| `OPENAI_API_KEY` | OpenAI API key ([API Keys](https://platform.openai.com/api-keys)) | Yes |
| `ADMIN_IDS` | Telegram user IDs for admins (comma-separated) | Yes |
| `YNAB_CLIENT_ID` | YNAB OAuth app client ID ([Developer Settings](https://app.ynab.com/settings/developer)) | Yes |
| `YNAB_CLIENT_SECRET` | YNAB OAuth app client secret | Yes |
| `YNAB_REDIRECT_URI` | OAuth callback URL (e.g. `https://your-domain.up.railway.app/oauth/callback`) | Yes |
| `TOKEN_ENCRYPTION_KEY` | Fernet key for encrypting tokens at rest (see below) | Yes |
| `HTTP_API_KEY` | Bearer token required for authenticated HTTP API endpoints | Yes |
| `DATABASE_PATH` | Path to SQLite database (users + learning data) | No (default: `data/users.db`) |

**Generate a Fernet encryption key:**
```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### 4. Run
```bash
python main.py     # Starts the bot
```

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

The bot supports shared expenses with automatic YNAB subtransactions:

```
"Almuerzo compartido con Juan 30k"           → 50/50 split, user paid
"Cena con María 60k, ella pagó"              → 50/50 split, third-party paid
"Juan pagó 100k de mercado por mí"           → 100% debt, third-party paid
```

**User-paid split**: Creates subtransactions splitting the amount between the real category and the Splitwise tracking category.

**Third-party paid split**: Creates a zero-sum transaction — the real category outflow is balanced by an inflow from the Splitwise tracking category, so your budget reflects the debt without affecting your account balance.

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
4. Bot exchanges the code for access + refresh tokens, encrypts them with Fernet, and stores in SQLite
5. Tokens are automatically refreshed when expired

**Security:**
- OAuth state parameter signed with HMAC-SHA256 (using `YNAB_CLIENT_SECRET`) to prevent CSRF
- Tokens encrypted at rest with Fernet symmetric encryption (`TOKEN_ENCRYPTION_KEY`)
- Tokens are never logged

## 🧪 Tests

```bash
# Full suite
pytest

# Single test file
pytest tests/test_domain_models.py

# Single test class or method
pytest tests/test_domain_models.py::TestExpense::test_is_valid_basic

# Filter by name
pytest -k "test_predict_category"
```

## 🏗️ Architecture

Layered architecture with dependency injection:

```
main.py → DIContainer (infrastructure/container.py)
        → public HTTP server on $PORT (health + OAuth + HTTP API)
        → YNABTelegramBot (presentation/telegram/bot.py)
```

**Message processing flow:**
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
```

## 🚀 Deployment

The bot is configured for deployment on **Railway** with:

- **Test-gating**: Tests run before every deploy; failures cancel the deployment (`railway.toml`)
- **Health check**: Built-in HTTP server at `/` for Railway health probes
- **OAuth callback**: Same public HTTP server handles `/oauth/callback` for the YNAB OAuth flow
- **Authenticated API**: Same public HTTP server also exposes `POST /api/v1/expenses/text`

To use the HTTP endpoint after deploy, set `HTTP_API_KEY` in Railway and call the same service domain at `/api/v1/expenses/text`.

### YNAB OAuth App Setup

1. Go to [YNAB Developer Settings](https://app.ynab.com/settings/developer)
2. Create a new OAuth Application
3. Set the Redirect URI to `https://<your-railway-domain>/oauth/callback`
4. Copy the Client ID and Client Secret to your environment variables

## 🛠️ Development Workflow

Feature development follows an AI-agnostic multi-agent pipeline. See [docs/AI_WORKFLOW.md](docs/AI_WORKFLOW.md) for the universal protocol, and [CLAUDE.md](CLAUDE.md) or [GEMINI.md](GEMINI.md) for AI-specific routing and role mapping.
