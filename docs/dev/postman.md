# Postman Guide

This guide covers the committed Postman bundle for the current HTTP surface.

Artifacts live in `docs/dev/postman/`:

- `ynab-bot-devex.postman_collection.json`
- `local-http-dev.postman_environment.json`
- `railway-http.postman_environment.json`

The bundle is intentionally small and tracks the current endpoints only:

- `POST /api/v1/expenses/text`
- `POST /dev/bootstrap`
- `POST /dev/messages/text`

## Import into Postman

Import the collection:

- `docs/dev/postman/ynab-bot-devex.postman_collection.json`

Then import one environment:

- `docs/dev/postman/local-http-dev.postman_environment.json`
- `docs/dev/postman/railway-http.postman_environment.json`

After import, duplicate the environment in Postman if you want a private working copy with real values.

## Variables

The collection expects these variables:

- `base_url`
- `http_api_key`
- `dev_api_key`
- `telegram_user_id`
- `expense_text`
- `query_text`
- `command_text`

Auth split:

- `HTTP_API_KEY` protects `POST /api/v1/expenses/text`
- `DEV_API_KEY` protects `/dev/*`

Do not reuse `DEV_API_KEY` in production environments.

## Local Workflow

Use the `Local HTTP Dev` environment for daily development.

Prerequisites:

1. Copy and fill `config/.env.dev`
2. Start the app:

```bash
docker compose up app-dev
```

3. In Postman, select `Local HTTP Dev`
4. Set the environment values to match your local `config/.env.dev`

Recommended request order:

1. `Local Dev Harness / Bootstrap Local User`
2. `Local Dev Harness / Simulate Command /status`
3. `Local Dev Harness / Simulate Expense Message`
4. `Production API / Log Expense`

Notes:

- `/dev/*` only works when `APP_MODE=http-dev` and `ENABLE_DEV_ROUTES=true`
- `APP_MODE=http-dev` is intentionally blocked on Railway
- local expense behavior depends on whether the bootstrapped user has `confirmation_mode` enabled

## Railway Workflow

Use the `Railway HTTP` environment only for the real authenticated API.

Set:

- `base_url` to your Railway domain
- `http_api_key` to the Railway `HTTP_API_KEY`
- `telegram_user_id` to a real configured user

Do not use or enable `dev_api_key` there. `/dev/*` is not a valid production surface.

Recommended Railway requests:

1. `Production API / Log Expense`
2. `Production API / Log Expense Force Commit`
3. `Production API / Reject Query Intent`
4. `Production API / Missing or Invalid HTTP API Key`

## Request Notes

### `POST /api/v1/expenses/text`

Body:

```json
{
  "telegram_user_id": 42,
  "text": "Gaste 25k en Carulla",
  "force_commit": false
}
```

Expected outcomes:

- `status=preview` when confirmation is required and `force_commit=false`
- `status=committed` when the expense is logged
- `422` for query intents or unprocessable messages

### `POST /dev/bootstrap`

Creates or updates a local authorized user and can simulate configured YNAB state.

### `POST /dev/messages/text`

Interprets leading `/` as a simulated command and all other text as a regular user message.

Supported command examples in the collection:

- `/start`
- `/status`
- `/budgets`
- `/accounts`
- `/resumen`

## Security Rules

- Commit only the example environment files in `docs/dev/postman/`
- Do not commit exported personal environments with real secrets
- Keep `DEV_API_KEY` local-only
- Do not run local dev routes on public or shared environments

## Maintenance

When the HTTP surface changes:

1. update the collection
2. update example environments if variables changed
3. update this guide and `docs/dev/README.md`

The collection is hand-maintained because the project does not currently publish an OpenAPI spec.
