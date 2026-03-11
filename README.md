# 🤖 YNAB Telegram Bot

A multi-user Telegram bot that logs expenses to YNAB (You Need A Budget) using OpenAI GPT-4o-mini for natural language parsing and Whisper for voice transcription. Targeted at Spanish-speaking users managing budgets in Colombian pesos.

## ✨ Features

- 🎤 **Voice Recognition**: Send audio messages and the bot transcribes them automatically with Whisper
- 🧠 **AI-Powered**: Uses OpenAI GPT-4o-mini to understand expenses and budget queries in natural Spanish language
- 📊 **Budget Queries**: Ask about category balances, account balances, or get a budget summary in natural language
- 📚 **Adaptive Learning**: Remembers your spending patterns and improves over time
- 💳 **Account Detection**: Automatically identifies the bank account mentioned
- 🏪 **Smart Categorization**: Assigns real YNAB categories based on merchant/location
- 👥 **Multi-User**: Authentication system with admin approval
- 🔐 **Per-User OAuth**: Each user connects their own YNAB account via OAuth2
- ✏️ **Correction System**: Manually correct categories and teach the bot
- 📊 **Statistics**: View learning progress and accuracy improvements

## 📁 Project Structure

```
ynab-bot/
├── main.py                          # Entry point
├── setup.py                         # Initialization script
├── requirements.txt                 # Python dependencies
├── pytest.ini                       # Test configuration
├── railway.toml                     # Railway deployment config (test-gating)
├── src/
│   ├── domain/                      # Models, interfaces, exceptions
│   │   ├── models/                  # Expense, BudgetQueryResult, UserConfiguration (with OAuth fields)
│   │   ├── repositories/           # Abstract interfaces (ABC)
│   │   ├── services/               # AuthorizationService
│   │   └── exceptions.py           # Includes OAuthException, TokenExpiredException
│   ├── application/services/        # Business logic orchestrators
│   │   ├── expense_service.py       # Pipeline: parse→enhance→create→learn + query routing
│   │   ├── budget_query_service.py  # Budget queries (category/account balance, summary)
│   │   ├── user_config_service.py   # Per-user configuration
│   │   ├── oauth_service.py         # YNAB OAuth2 lifecycle (auth, tokens, refresh)
│   │   └── learning_service.py
│   ├── infrastructure/
│   │   ├── config/app_config.py     # Loads config/.env
│   │   ├── container.py             # Dependency injection (DIContainer)
│   │   ├── health.py                # Health check + OAuth callback HTTP server
│   │   ├── token_encryption.py      # Fernet encryption for tokens at rest
│   │   └── repositories/           # SQLite, YNAB API, YNABRepositoryFactory
│   ├── presentation/telegram/
│   │   ├── bot.py                   # Handler registration
│   │   ├── formatters.py           # Message formatting
│   │   ├── handlers/               # General, Config, Expense, Learning, Admin
│   │   └── middleware/             # @require_authentication, @require_admin
│   ├── parsers/
│   │   └── llm_expense_parser.py    # GPT-4o-mini parser
│   └── integrations/
│       └── speech_to_text.py        # Whisper transcription
├── config/
│   ├── .env                         # Environment variables (private)
│   └── .env.example                 # Configuration template
├── data/                            # Persistent data
│   └── users.db                     # SQLite database (users + learning data)
└── tests/                           # Test suite (~349 tests, ~86% coverage)
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
| `DATABASE_PATH` | Path to SQLite database (users + learning data) | No (default: `data/users.db`) |

**Generate a Fernet encryption key:**
```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### 4. Initialize and run
```bash
python setup.py   # Creates directory structure and data files
python main.py     # Starts the bot
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

**Learning:**
- `/stats` — Learning statistics
- `/recent` — View recent transactions
- `/corregir` — Correct a transaction's category

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
```

Amount formats: `40000`, `40 mil`, `40 lucas`, `40k`, `$40000`, decimals with comma (`40000,50`).

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

### Correction and Learning System

1. Use `/corregir` to view recent transactions
2. Select the transaction to correct
3. Choose the correct category from your YNAB categories
4. The bot learns from the correction for future transactions

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
# Full suite (~349 tests, ~86% coverage)
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
main.py → DIContainer (infrastructure/container.py) → YNABTelegramBot (presentation/telegram/bot.py)
```

**Message processing flow:**
```
User (text)
  → ExpenseService.process_message()
    → LLMExpenseParser.parse_message() → classifies intent ("expense" | "query")
    → LLM semantically maps user terms to exact YNAB category/account names
    → if expense: parse→enhance→create→learn pipeline
    → if query: BudgetQueryService (4-step fuzzy fallback) → category/account/summary data
  → Formatted Telegram response

User (voice)
  → Whisper transcription
  → ExpenseService.process_expense_message() → expense pipeline
```

## 🚀 Deployment

The bot is configured for deployment on **Railway** with:

- **Test-gating**: Tests run before every deploy; failures cancel the deployment (`railway.toml`)
- **Health check**: Built-in HTTP server at `/` for Railway health probes
- **OAuth callback**: Same HTTP server handles `/oauth/callback` for the YNAB OAuth flow

### YNAB OAuth App Setup

1. Go to [YNAB Developer Settings](https://app.ynab.com/settings/developer)
2. Create a new OAuth Application
3. Set the Redirect URI to `https://<your-railway-domain>/oauth/callback`
4. Copy the Client ID and Client Secret to your environment variables
