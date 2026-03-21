# Migration Guide: Layered Architecture Refactoring

## Overview

The YNAB Telegram Bot has been refactored from a monolithic architecture to a clean, layered architecture following Domain-Driven Design (DDD) principles.

## New Architecture

```
src/
├── domain/                    # Business models and rules
│   ├── models/               # Domain entities
│   │   ├── expense.py       # Expense and ExpenseResult models  
│   │   └── user.py          # User, Budget, Account, Category models
│   ├── repositories/        # Repository interfaces
│   │   ├── user_repository.py
│   │   ├── ynab_repository.py
│   │   └── learning_repository.py
│   └── exceptions.py        # Domain exceptions
├── application/              # Use cases and services
│   └── services/            # Application services
│       ├── expense_service.py
│       ├── user_config_service.py
│       └── learning_service.py
├── infrastructure/          # External concerns
│   ├── config/             # Configuration management
│   │   └── app_config.py
│   ├── repositories/       # Repository implementations
│   │   ├── sqlite_user_repository.py
│   │   ├── ynab_api_repository.py
│   │   └── json_learning_repository.py
│   └── container.py        # Dependency injection
└── presentation/           # User interface
    └── telegram/          # Telegram-specific UI
        ├── handlers/      # Command handlers
        │   ├── expense_handler.py
        │   ├── config_handler.py
        │   ├── learning_handler.py
        │   └── general_handler.py
        ├── formatters.py  # Response formatting
        └── bot.py        # Main bot class
```

## Key Changes

### 1. Dependency Injection
- **Before**: Direct instantiation throughout the code
- **After**: All dependencies injected through `DIContainer`

### 2. Domain Models  
- **Before**: Raw dictionaries passed around
- **After**: Proper `@dataclass` models with validation

### 3. Repository Pattern
- **Before**: Direct file/database access in business logic
- **After**: Abstract repositories with clean interfaces

### 4. Service Layer
- **Before**: Business logic mixed with presentation
- **After**: Dedicated service classes handling use cases

### 5. Handler Separation
- **Before**: Single 720-line monolithic bot class
- **After**: Focused handlers for different command types

## Running the Refactored Bot

The entry point remains the same:

```bash
python main.py
```

The new `main.py` now:
1. Creates a dependency injection container
2. Initializes the layered bot architecture  
3. Runs with proper error handling and logging

## Configuration

Configuration is now centralized in `AppConfig`:

```python
from infrastructure.config.app_config import AppConfig

config = AppConfig.from_env('config/.env')
```

Required environment variables remain the same:
- `TELEGRAM_BOT_TOKEN`
- `YNAB_ACCESS_TOKEN` 
- `OPENAI_API_KEY`
- `YNAB_BUDGET_ID` (optional)

## Benefits of New Architecture

1. **Testability**: Each layer can be unit tested independently
2. **Maintainability**: Clear separation of concerns
3. **Scalability**: Easy to add new features without touching existing code
4. **Flexibility**: Can easily swap implementations (different databases, APIs)
5. **Code Reuse**: Business logic can be reused in different contexts

## Backward Compatibility

All existing functionality is preserved:
- All commands work exactly the same
- Learning system continues with existing data
- User configurations are maintained
- YNAB integration unchanged

## Old Implementation

The original monolithic implementation is preserved in:
- `src/bot/telegram_bot.py` (original)
- `src/bot/telegram_bot_backup.py` (backup if exists)

## Testing the Migration

1. **Configuration Test**:
   ```bash
   python -c "from infrastructure.container import create_container; print('✅ Container created')"
   ```

2. **Service Test**:
   ```bash  
   python -c "from infrastructure.container import create_container; c = create_container(); print('✅ Services loaded')"
   ```

3. **Full Bot Test**:
   ```bash
   python main.py
   ```

## Migration Verification

To verify the migration was successful:

1. ✅ Bot starts without errors
2. ✅ `/start` command works  
3. ✅ `/config` shows configuration options
4. ✅ `/help` displays help message
5. ✅ Expense messages are processed
6. ✅ Voice messages work (if OpenAI key configured)
7. ✅ Learning system statistics available via `/stats`

## Rollback Plan

If needed, you can rollback by:

1. Restoring the original `main.py`:
   ```python
   from bot.telegram_bot import YNABTelegramBot
   bot = YNABTelegramBot()
   bot.run()
   ```

2. The old implementation files are preserved and functional

## Next Steps

With the new architecture in place, you can now:

1. **Add Tests**: Each service can be unit tested independently
2. **Add New Features**: Follow the layered approach for new functionality  
3. **Optimize Performance**: Add caching layers easily
4. **Scale**: Add new presentation layers (web interface, CLI, etc.)
5. **Monitor**: Add observability at each layer

The codebase is now ready for professional development and maintenance!