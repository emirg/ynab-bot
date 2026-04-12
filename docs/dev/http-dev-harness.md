# HTTP Dev Harness Reference

This document covers the local development harness exposed through `/dev/*` when:

```env
APP_MODE=http-dev
ENABLE_DEV_ROUTES=true
```

These routes are intended for local-only workflows. They are not part of the production API surface.

## Auth

All dev routes require:

```http
Authorization: Bearer <DEV_API_KEY>
Content-Type: application/json
```

If `DEV_API_KEY` is missing, `http-dev` will not start.
If `ENABLE_DEV_ROUTES=true` is not set, `/dev/*` is not mounted even in `http-dev`.

## Base URL

Default local base URL:

```text
http://localhost:8080
```

## Endpoints

### `POST /dev/bootstrap`

Creates or updates a local development user and optionally simulates YNAB-connected/configured state.

Request body:

```json
{
  "telegram_user_id": 42,
  "first_name": "Dev",
  "username": "devuser",
  "ynab_connected": true,
  "configured": true,
  "confirmation_mode": false
}
```

Fields:

- `telegram_user_id`
  Integer. Defaults to `1`.
- `first_name`
  Optional. Defaults to `"Dev"`.
- `username`
  Optional. Defaults to `"devuser"`.
- `ynab_connected`
  Optional boolean. Defaults to `true`.
- `configured`
  Optional boolean. Defaults to `true`.
- `confirmation_mode`
  Optional boolean. Defaults to `false`.

Behavior:

- creates the user if missing
- marks the user as authorized
- simulates YNAB tokens when `ynab_connected=true`
- bootstraps a budget and default account when supported by the stubbed YNAB factory
- optionally leaves the user partially configured

Example:

```bash
curl -X POST http://localhost:8080/dev/bootstrap \
  -H "Authorization: Bearer $DEV_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"telegram_user_id": 42}'
```

Typical success response:

```json
{
  "status": "ok",
  "telegram_user_id": 42,
  "onboarding_step": "complete",
  "user_status": {
    "configured": true,
    "budget_id": "budget-dev-main",
    "budget_name": "Dev Budget",
    "default_account_id": "acc-dev-nu",
    "default_account_name": "Nu Card",
    "ynab_connected": true,
    "message": "Usuario completamente configurado"
  }
}
```

### `POST /dev/messages/text`

Simulates either a Telegram command or a regular text message.

Request body:

```json
{
  "telegram_user_id": 42,
  "text": "Gaste 25k en Carulla",
  "force_commit": false
}
```

Fields:

- `telegram_user_id`
  Integer. Required.
- `text`
  String. Required.
- `force_commit`
  Optional boolean. Used when confirmation mode is enabled.

Behavior:

- if `text` starts with `/`, it is treated as a simulated command
- otherwise it is treated as a regular text message
- it reuses the existing service layer instead of creating a second business path

## Supported Commands

The harness currently supports:

- `/start`
- `/status`
- `/budgets`
- `/accounts`
- `/resumen`

Unsupported commands return:

- `404`
- `COMMAND_NOT_SUPPORTED`

## Response Shapes

### Simulated command

Example request:

```bash
curl -X POST http://localhost:8080/dev/messages/text \
  -H "Authorization: Bearer $DEV_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"telegram_user_id": 42, "text": "/status"}'
```

Example response:

```json
{
  "status": "ok",
  "kind": "command",
  "command": "/status",
  "message": "..."
}
```

### Simulated expense message

Example request:

```bash
curl -X POST http://localhost:8080/dev/messages/text \
  -H "Authorization: Bearer $DEV_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"telegram_user_id": 42, "text": "Gaste 25k en Carulla"}'
```

Success response:

```json
{
  "status": "ok",
  "kind": "message",
  "intent": "expense",
  "message": "...",
  "transaction_id": "dev-txn-..."
}
```

### Preview response

If the user has confirmation mode enabled and `force_commit=false`:

```json
{
  "status": "preview",
  "kind": "message",
  "intent": "expense",
  "message": "..."
}
```

### Query-like message

If the stub parser classifies the message as a query:

```json
{
  "status": "ok",
  "kind": "message",
  "intent": "query",
  "message": "..."
}
```

### Error response

Example:

```json
{
  "status": "error",
  "error_code": "USER_NOT_FOUND",
  "message": "No registered user exists for that telegram_user_id."
}
```

## Helper Scripts

The project includes two CLI helpers for the harness.

### `scripts/dev/bootstrap_user.py`

Bootstraps a user through `POST /dev/bootstrap`.

Example:

```bash
.venv/bin/python scripts/dev/bootstrap_user.py \
  --dev-api-key "$DEV_API_KEY" \
  --telegram-user-id 42 \
  --confirmation-mode
```

Available flags:

- `--base-url`
- `--dev-api-key`
- `--telegram-user-id`
- `--first-name`
- `--username`
- `--no-ynab`
- `--not-configured`
- `--confirmation-mode`

### `scripts/dev/send_message.py`

Sends a simulated command or text message through `POST /dev/messages/text`.

Examples:

```bash
.venv/bin/python scripts/dev/send_message.py "/start" \
  --dev-api-key "$DEV_API_KEY" \
  --telegram-user-id 42

.venv/bin/python scripts/dev/send_message.py "Gaste 25k en Carulla" \
  --dev-api-key "$DEV_API_KEY" \
  --telegram-user-id 42
```

Available flags:

- positional `text`
- `--base-url`
- `--dev-api-key`
- `--telegram-user-id`
- `--force-commit`

## Limitations

- These routes do not connect to real Telegram.
- In `http-dev`, these routes do not use real OpenAI or YNAB.
- The supported command set is intentionally small and focused on common local workflows.
- Voice, photo, and callback-query simulation are not implemented in this first DX version.
