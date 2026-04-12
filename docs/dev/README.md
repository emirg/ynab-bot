# Local Development Guide

This directory documents the local developer experience for the project.

The current preferred workflow is `HTTP-first` local development:

- run the app locally without competing with the Railway Telegram polling instance
- keep SQLite as the default local database
- use stubbed OpenAI and YNAB integrations by default
- simulate Telegram-like flows through local dev endpoints and helper scripts

Related docs:

- `docs/dev/http-dev-harness.md` — local `/dev/*` endpoints and helper scripts
- `README.md` — project overview and high-level commands
- `docs/ARCHITECTURE.md` — runtime architecture

## Goals

The local workflow is designed to optimize for:

- fast startup
- safe local experimentation
- no dependency on the production Telegram bot token
- no dependency on live OpenAI or YNAB credentials for daily work
- reproducible setup through Docker and env templates

## Prerequisites

You need:

- Docker and Docker Compose
- Python `3.12+`
- the project virtual environment at `.venv`

Recommended local bootstrap:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Local Modes

The runtime supports multiple modes through environment variables:

- `APP_MODE=full`
  Production-like mode. Starts the public HTTP server and real Telegram polling.
- `APP_MODE=http-dev`
  Local development mode. Starts the public HTTP server, enables `/dev/*`, and disables Telegram polling.
- `APP_MODE=http-live`
  HTTP-only mode with live integrations and no Telegram polling.
- `APP_MODE=test`
  Test-oriented mode.

Integration behavior is controlled separately:

- `EXTERNAL_MODE=stub`
  Use local stubs for OpenAI and YNAB.
- `EXTERNAL_MODE=live`
  Use real OpenAI and YNAB integrations.

Default local development uses:

```env
APP_MODE=http-dev
EXTERNAL_MODE=stub
ENABLE_DEV_ROUTES=true
```

## Required Local Files

Copy the local env template:

```bash
cp config/.env.dev.example config/.env.dev
```

At minimum, set these values in `config/.env.dev`:

- `TOKEN_ENCRYPTION_KEY`
- `HTTP_API_KEY`
- `DEV_API_KEY`
- `ENABLE_DEV_ROUTES=true`
- `ADMIN_IDS`
- `DATABASE_PATH`

Notes:

- `DEV_API_KEY` is explicitly required in `http-dev` mode.
- `ENABLE_DEV_ROUTES=true` is also required if you want `/dev/*`.
- `HTTP_API_KEY` still protects the real `/api/v1/expenses/text` endpoint even in local mode.
- In `http-dev` mode, Telegram, OpenAI, and YNAB credentials are not required.

## Docker Workflows

### Daily local dev

```bash
docker compose up app-dev
```

What this starts:

- the app on `http://localhost:8080`
- `APP_MODE=http-dev`
- `EXTERNAL_MODE=stub`
- SQLite persistence using your local `DATABASE_PATH`
- localhost-only published ports

What it does not start:

- Telegram polling
- live OpenAI calls
- live YNAB calls

### Optional local Postgres

```bash
docker compose --profile postgres up postgres
```

Use this when working on database migration or integration scenarios that need PostgreSQL.

### Optional live integrations

```bash
docker compose --profile live-integrations up app-live
```

This mode:

- disables Telegram polling
- keeps the HTTP server
- uses real OpenAI and YNAB integrations

For this mode, you must fill in the live credentials in `config/.env.dev`.

## Daily Workflow

Recommended local loop:

1. Start the local app:

```bash
docker compose up app-dev
```

2. Bootstrap a local user:

```bash
.venv/bin/python scripts/dev/bootstrap_user.py --dev-api-key "$DEV_API_KEY"
```

3. Simulate commands or messages:

```bash
.venv/bin/python scripts/dev/send_message.py "/start" --dev-api-key "$DEV_API_KEY"
.venv/bin/python scripts/dev/send_message.py "/status" --dev-api-key "$DEV_API_KEY"
.venv/bin/python scripts/dev/send_message.py "Gaste 25k en Carulla" --dev-api-key "$DEV_API_KEY"
```

4. Run tests from the virtual environment:

```bash
.venv/bin/pytest
```

## Security Notes

- Do not commit `config/.env.dev`.
- Do not reuse production secrets in local development unless you intentionally need `http-live`.
- Do not enable `APP_MODE=http-dev` on Railway or any public environment.
- `/dev/*` routes only exist in `http-dev`, but they are still protected by `DEV_API_KEY` and should be treated as local-only tooling.
- `APP_MODE=http-dev` is blocked on Railway by startup validation.

## Troubleshooting

### App fails to start in `http-dev`

Check that `config/.env.dev` contains:

- `TOKEN_ENCRYPTION_KEY`
- `DEV_API_KEY`

### `/dev/*` returns `401`

Your `Authorization` header must be:

```http
Authorization: Bearer <DEV_API_KEY>
```

### `/dev/messages/text` returns `USER_NOT_FOUND`

Bootstrap a user first:

```bash
.venv/bin/python scripts/dev/bootstrap_user.py --dev-api-key "$DEV_API_KEY"
```

### I want real YNAB/OpenAI behavior locally

Use the live integrations profile and set the corresponding credentials in `config/.env.dev`:

```bash
docker compose --profile live-integrations up app-live
```
