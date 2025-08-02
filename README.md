# 🤖 YNAB Telegram Bot

An intelligent Telegram bot that automatically logs expenses to YNAB (You Need A Budget) using AI-powered natural language processing and voice recognition.

## ✨ Features

- 🎤 **Voice Recognition**: Send audio messages and the bot transcribes them automatically
- 🧠 **AI-Powered**: Uses OpenAI GPT to understand expenses in natural Spanish language
- 📚 **Adaptive Learning**: Remembers your spending patterns and improves over time
- 💳 **Account Detection**: Automatically identifies the bank account used
- 🏪 **Smart Categorization**: Assigns real YNAB categories based on merchant/location
- 🔄 **Full Integration**: Direct synchronization with your YNAB budget
- ✏️ **Correction System**: Manually correct categories and teach the bot
- 📊 **Real-time Stats**: View learning progress and accuracy improvements

## 📁 Project Structure

```
ynab-bot/
├── main.py                    # Main entry point
├── setup.py                   # Configuration script
├── requirements.txt           # Python dependencies
├── src/                       # Source code
│   ├── bot/                   # Telegram bot logic
│   │   └── telegram_bot.py    # Main bot implementation
│   ├── parsers/               # Expense processors
│   │   ├── smart_expense_parser.py      # Main intelligent parser
│   │   ├── llm_expense_parser.py        # AI parser (OpenAI)
│   │   └── adaptive_category_learner.py # Learning system
│   └── integrations/          # External integrations
│       ├── ynab_client.py              # YNAB API client
│       ├── ynab_category_manager.py    # Category manager
│       ├── ynab_account_manager.py     # Account manager
│       └── speech_to_text.py           # Audio transcription
├── data/                      # Persistent data
│   └── category_learning_data.json     # Learning data
├── config/                    # Configuration
│   ├── .env                   # Environment variables (private)
│   └── .env.example           # Configuration template
└── docs/                      # Documentation
```

## 🚀 Installation & Setup

### 1. Clone the repository
```bash
git clone <repository-url>
cd ynab-bot
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure environment variables
```bash
cp config/.env.example config/.env
```

Edit the `config/.env` file with your tokens:
- `TELEGRAM_BOT_TOKEN`: Your Telegram bot token
- `YNAB_ACCESS_TOKEN`: Your YNAB personal access token
- `YNAB_BUDGET_ID`: (Optional) Your default budget ID
- `OPENAI_API_KEY`: Your OpenAI API key

### 4. Setup Instructions

#### Create Telegram Bot
1. Chat with [@BotFather](https://t.me/botfather) on Telegram
2. Use the `/newbot` command
3. Follow the instructions to create your bot
4. Copy the token provided by BotFather

#### Get YNAB Token
1. Go to [YNAB Developer Settings](https://app.ynab.com/settings/developer)
2. Click "New Token"
3. Enter your password
4. Copy the generated token (keep it safe!)

#### Get OpenAI API Key
1. Go to [OpenAI API Keys](https://platform.openai.com/api-keys)
2. Create a new API key
3. Copy the key for your configuration

### 5. Run the Bot

```bash
python main.py
```

## 📱 Usage

### Available Commands

- `/start` - Welcome message and bot introduction
- `/help` - Help and usage examples
- `/config` - Configure YNAB budgets and accounts
- `/corregir` - Correct recent transaction categories
- `/stats` - View learning statistics and accuracy

### Supported Message Formats

The bot understands various natural language formats for logging expenses (in Spanish):

```
✅ "Gasté $50000 en comida en Éxito"
✅ "Me gasté 25000 pesos en transporte"
✅ "$30000 comida Carulla"
✅ "45000 pesos gasolina con mi tarjeta Nu"
✅ "Compré ropa por $80000 en Zara"
✅ "15000 entretenimiento Netflix"
✅ "Almuerzo 25000 en Home Burguer"
```

### Voice Messages

Send voice messages in Spanish and the bot will:
1. Transcribe the audio using OpenAI Whisper
2. Parse the expense information
3. Log it to YNAB automatically

### Account Detection

The bot can detect bank accounts mentioned in messages:
- "con mi tarjeta Nu" → Nu Card account
- "con Rappi Card" → Rappi Card account
- "efectivo" → Cash account

### Smart Categorization

The bot automatically categorizes expenses using:
- **Real YNAB categories**: Uses your actual budget categories
- **Merchant recognition**: Learns common stores and their categories
- **Adaptive learning**: Improves accuracy based on your corrections
- **Entretenimiento**: entretenimiento, cine, netflix, spotify, juegos
- **Salud**: salud, medicina, doctor, farmacia, hospital
- **Ropa**: ropa, vestimenta, zapatos, clothing
- **Servicios**: servicios, luz, agua, internet, teléfono
- **Restaurante**: restaurante, restaurant, comida rápida, delivery

## Estructura del Proyecto

```
ynab-bot/
├── telegram_bot.py      # Bot principal de Telegram
├── ynab_client.py       # Cliente para la API de YNAB
├── expense_parser.py    # Parser de mensajes de gastos
├── requirements.txt     # Dependencias de Python
├── .env.example        # Ejemplo de variables de entorno

## Seguridad

- ⚠️ **Nunca compartas tus tokens** - Mantenlos seguros y privados
- 🔒 **Usa variables de entorno** - No hardcodees tokens en el código
- 🚫 **No subas el archivo .env** - Está en .gitignore por seguridad

### Correction System

The bot includes a powerful correction system:

1. **View recent transactions**: Use `/corregir` to see recent expenses
2. **Select transaction**: Choose the transaction you want to correct
3. **Pick new category**: Select from all your YNAB categories
4. **Automatic learning**: The bot learns from your corrections

### Learning Statistics

Use `/stats` to view:
- Total transactions processed
- Learned merchant associations
- Accuracy improvements over time
- Current learning confidence levels

## 🎨 Technical Architecture

### Core Components

- **Smart Expense Parser**: Main parsing engine that coordinates all processing
- **LLM Expense Parser**: OpenAI GPT-powered natural language understanding
- **Adaptive Category Learner**: Machine learning system that improves over time
- **YNAB Integration**: Full API integration with real-time category and account sync
- **Speech-to-Text**: OpenAI Whisper for voice message transcription

### Data Flow

1. **Input**: Text or voice message in Spanish
2. **Transcription**: Voice messages converted to text (if applicable)
3. **AI Parsing**: OpenAI GPT extracts amount, merchant, category, account
4. **Category Matching**: Real YNAB categories matched using intelligent search
5. **Account Detection**: Bank accounts identified from natural language
6. **Learning**: Adaptive system learns merchant-category associations
7. **YNAB Sync**: Transaction created in your YNAB budget
8. **Feedback**: Confirmation with parsing details and confidence

### Currency Support

Designed for Colombian Pesos (COP):
- Supports comma decimal separator (e.g., "40000,56")
- Handles large amounts common in COP
- Recognizes peso-specific formatting

## 🛠️ Dependencies

- `python-telegram-bot` - Telegram bot framework
- `requests` - HTTP client for YNAB API
- `openai` - OpenAI API client for GPT and Whisper
- `python-dotenv` - Environment variable management
- `logging` - Comprehensive logging system

## 🤝 Contributing

1. Fork the project
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📝 License

Distributed under the MIT License. See `LICENSE` for more information.

## 📞 Support

If you encounter any issues or have questions:
1. Check the logs for detailed error information
2. Ensure all API keys are correctly configured
3. Verify YNAB budget and account access
4. Test with simple expense messages first

## 🎆 Roadmap

- [ ] Multi-language support (English, Portuguese)
- [ ] Web dashboard for statistics and configuration
- [ ] Receipt photo processing with OCR
- [ ] Recurring transaction templates
- [ ] Budget alerts and notifications
- [ ] Multi-user support with authentication
