# 🤖 YNAB Telegram Bot

A multi-user Telegram bot that logs expenses to YNAB (You Need A Budget) using OpenAI GPT-4o-mini for natural language parsing and Whisper for voice transcription. Targeted at Spanish-speaking users managing budgets in Colombian pesos.

## ✨ Features

- 🎤 **Voice Recognition**: Send audio messages and the bot transcribes them automatically with Whisper
- 🧠 **AI-Powered**: Uses OpenAI GPT-4o-mini to understand expenses in natural Spanish language
- 📚 **Adaptive Learning**: Remembers your spending patterns and improves over time
- 💳 **Account Detection**: Automatically identifies the bank account mentioned
- 🏪 **Smart Categorization**: Assigns real YNAB categories based on merchant/location
- 👥 **Multi-User**: Authentication system with admin approval
- ✏️ **Correction System**: Manually correct categories and teach the bot
- 📊 **Statistics**: View learning progress and accuracy improvements

## 📁 Project Structure

```
ynab-bot/
├── main.py                          # Entry point
├── setup.py                         # Initialization script
├── requirements.txt                 # Python dependencies
├── pytest.ini                       # Test configuration
├── src/
│   ├── domain/                      # Models, interfaces, exceptions
│   │   ├── models/                  # Expense, UserConfiguration
│   │   ├── repositories/           # Abstract interfaces (ABC)
│   │   ├── services/               # AuthorizationService
│   │   └── exceptions.py
│   ├── application/services/        # Business logic orchestrators
│   │   ├── expense_service.py       # Pipeline: parse→enhance→create→learn
│   │   ├── user_config_service.py   # Per-user configuration
│   │   └── learning_service.py
│   ├── infrastructure/
│   │   ├── config/app_config.py     # Loads config/.env
│   │   ├── container.py             # Dependency injection (DIContainer)
│   │   └── repositories/           # SQLite, YNAB API, JSON learning
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
│   ├── users.db                     # SQLite user database
│   └── category_learning_data.json  # Learning data
└── tests/                           # Test suite (265 tests, ~84% coverage)
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
| `YNAB_ACCESS_TOKEN` | YNAB personal access token ([Developer Settings](https://app.ynab.com/settings/developer)) | Yes |
| `YNAB_BUDGET_ID` | Your YNAB budget ID | Yes |
| `OPENAI_API_KEY` | OpenAI API key ([API Keys](https://platform.openai.com/api-keys)) | Yes |
| `ADMIN_IDS` | Telegram user IDs for admins (comma-separated) | Yes |
| `DATABASE_PATH` | Path to SQLite database | No (default: `data/users.db`) |
| `LEARNING_DATA_PATH` | Path to learning data file | No (default: `data/category_learning_data.json`) |

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

**Configuration:**
- `/config` — Configure YNAB budget and accounts
- `/budgets` — List available budgets
- `/accounts` — List available accounts
- `/status` — View current configuration

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

## 👥 Authentication System

The bot implements a multi-user system with admin approval:

1. A new user sends `/start` → status set to **PENDING**
2. All other commands are blocked until approved
3. An admin reviews the request with `/pending` and approves or blocks
4. The user receives a notification and can start using the bot
5. Must configure their budget (`/budgets`) and account (`/accounts`) before logging expenses

User statuses: `PENDING` → `AUTHORIZED` | `BLOCKED`

## 🧪 Tests

```bash
# Full suite (265 tests, ~84% coverage)
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

**Expense processing flow:**
```
User (text/voice)
  → Whisper (if voice)
  → ExpenseService.process_expense_message()
    → LLMExpenseParser (GPT-4o-mini: extracts amount, category, payee, account)
    → LearningRepository.predict_category() (frequency-based, confidence ≥0.6)
    → YNABApiRepository.create_transaction()
    → LearningRepository.record_successful_transaction()
```
