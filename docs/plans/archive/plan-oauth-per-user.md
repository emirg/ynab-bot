# Plan: OAuth por Usuario para YNAB

## Metadata
- **Harness Roadmap:** Ignore

## Contexto

Actualmente todos los usuarios del bot comparten un único `YNAB_ACCESS_TOKEN` global. Esto limita el sistema a una sola cuenta YNAB. El objetivo es permitir que cada usuario conecte su propia cuenta YNAB mediante OAuth2, manteniendo el token global como fallback durante la transición.

## Pre-requisito Manual

1. Registrar una OAuth Application en https://app.ynab.com/settings/developer
2. Configurar Redirect URI: `https://<dominio-railway>/oauth/callback`
3. Generar dominio público en Railway para el servicio
4. Agregar variables de entorno: `YNAB_CLIENT_ID`, `YNAB_CLIENT_SECRET`, `YNAB_REDIRECT_URI`, `TOKEN_ENCRYPTION_KEY`
5. Eliminar `YNAB_ACCESS_TOKEN` (ya no se usa)

## Orden de Implementación

### Paso 1: Excepciones nuevas
**Archivo:** `src/domain/exceptions.py`
- Agregar `OAuthException(YNABBotException)` y `TokenExpiredException(YNABApiException)`

### Paso 2: Modelo de dominio
**Archivo:** `src/domain/models/user.py`
- Agregar campos a `UserConfiguration`: `ynab_access_token`, `ynab_refresh_token`, `ynab_token_expires_at`
- Agregar métodos: `has_ynab_token()`, `is_token_expired()`, `update_ynab_tokens()`, `clear_ynab_tokens()`
- **Tests:** `tests/test_domain_models.py`

### Paso 3: Migración de BD
**Archivo:** `src/infrastructure/repositories/database_manager.py`
- Migración v3: `ALTER TABLE user_configurations ADD COLUMN` para los 3 campos de token

### Paso 4: Repositorio de usuarios
**Archivo:** `src/infrastructure/repositories/sqlite_user_repository.py`
- Actualizar `_row_to_user_config` y `save()` para mapear las columnas nuevas
- Cifrado/descifrado de tokens con `cryptography.fernet` al leer/escribir
- **Tests:** `tests/test_sqlite_user_repository.py`

### Paso 5: AppConfig
**Archivo:** `src/infrastructure/config/app_config.py`
- Agregar campos opcionales: `ynab_client_id`, `ynab_client_secret`, `ynab_redirect_uri`, `token_encryption_key`
- Cambiar `ynab_token` de obligatorio a opcional
- Agregar `is_oauth_configured() -> bool`
- Validar que al menos un modo esté configurado (token global u OAuth)
- **Tests:** `tests/test_app_config.py`

### Paso 6: Servicio OAuth (nuevo)
**Archivo:** `src/application/services/oauth_service.py`
- `YNABOAuthService` con: `generate_auth_url()`, `exchange_code_for_tokens()`, `refresh_token_if_needed()`, `get_valid_access_token()`, `disconnect_user()`
- State firmado con HMAC-SHA256 usando `YNAB_CLIENT_SECRET` para vincular callback con `telegram_user_id`
- **Tests:** `tests/test_oauth_service.py`

### Paso 7: YNABRepositoryFactory (nuevo)
**Archivo:** `src/infrastructure/repositories/ynab_api_repository.py`
- Agregar clase `YNABRepositoryFactory` en el mismo archivo
- `get_repository(user_config)` → obtiene token via `oauth_service.get_valid_access_token()`, lanza error si no tiene token
- `YNABApiRepository` no cambia internamente, solo cambia cómo se instancia
- **Tests:** `tests/test_ynab_repository_factory.py`

### Paso 8: Actualizar servicios de aplicación
**Archivos:**
- `src/application/services/expense_service.py` — cambiar `ynab_repository` → `ynab_factory`, obtener repo per-user después de cargar `user_config`
- `src/application/services/user_config_service.py` — mismo cambio; `get_available_budgets()` ahora recibe `telegram_user_id`
- **Tests:** actualizar `tests/test_expense_service.py` y `tests/test_user_config_service.py`

### Paso 9: DI Container
**Archivo:** `src/infrastructure/container.py`
- Registrar `YNABOAuthService` y `YNABRepositoryFactory` como singletons
- Remover singleton de `YNABApiRepository`
- Actualizar creación de `ExpenseService` y `UserConfigService` para usar factory

### Paso 10: Endpoint OAuth callback
**Archivo:** `src/infrastructure/health.py`
- Extender `_HealthHandler.do_GET` para manejar `/oauth/callback`
- Parsear `code` y `state`, llamar `oauth_service.exchange_code_for_tokens()`
- Responder con HTML de confirmación en español
- `start_health_server()` recibe `oauth_service` como parámetro opcional
- **Tests:** `tests/test_health.py`

### Paso 11: Handlers de Telegram
**Archivo:** `src/presentation/telegram/handlers/config_handler.py`
- Nuevo comando `/connect` → genera URL OAuth y la envía al usuario
- Nuevo comando `/disconnect` → elimina tokens y resetea config
- Actualizar `/config` para mostrar estado de conexión YNAB
- Actualizar `/status` para mostrar si usa token propio o global

**Archivo:** `src/presentation/telegram/bot.py`
- Registrar handlers para `/connect` y `/disconnect`

### Paso 12: Wiring final
**Archivos:**
- `main.py` — pasar `oauth_service` a `start_health_server()`
- `requirements.txt` — agregar `cryptography`
- `config/.env.example` — documentar nuevas variables
- `tests/conftest.py` — fixtures: `mock_oauth_service`, `mock_ynab_factory`

## Seguridad
- **Cifrado en reposo**: tokens cifrados con Fernet (`cryptography` library) antes de guardar en SQLite, descifrados al leer. Cifrado/descifrado en `SQLiteUserRepository`
- **Variable requerida**: `TOKEN_ENCRYPTION_KEY` (generar con `Fernet.generate_key()`)
- **Dependencia nueva**: `cryptography` en `requirements.txt`
- State OAuth firmado con HMAC-SHA256 para prevenir CSRF
- HTTPS garantizado por Railway en dominios generados
- Tokens nunca se loguean

## Modelo de autenticación
- **Solo OAuth**: se elimina el soporte para `YNAB_ACCESS_TOKEN` global
- Todos los usuarios deben conectar su propia cuenta YNAB via `/connect`
- Usuarios existentes deberán reconectarse
- `YNAB_ACCESS_TOKEN` se elimina de AppConfig y de `.env.example`
- Los servicios que necesitan YNAB fallan con mensaje claro si el usuario no tiene token OAuth

## Verificación
1. `pytest` — todos los tests existentes + nuevos deben pasar
2. Flujo manual: `/connect` → abrir URL → autorizar en YNAB → callback → `/status` muestra token propio
3. Registrar un gasto y verificar que usa el token del usuario
4. Verificar que usuarios sin OAuth siguen funcionando con token global
