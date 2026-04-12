# Local Development Guide

This directory documents the local developer experience for the project.

The current preferred workflow is `HTTP-first` local development:

- run the app locally without competing with the Railway Telegram polling instance
- use PostgreSQL as the runtime database baseline
- use stubbed OpenAI and YNAB integrations by default
- simulate Telegram-like flows through local dev endpoints and helper scripts

Related docs:

- `docs/dev/http-dev-harness.md` — local `/dev/*` endpoints and helper scripts
- `docs/dev/postman.md` — Postman collection, environments, and request order
- `docs/dev/railway-postgres-cutover.md` — production migration and rollback runbook
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
- `POSTGRES_DSN`

Notes:

- `DEV_API_KEY` is explicitly required in `http-dev` mode.
- `ENABLE_DEV_ROUTES=true` is also required if you want `/dev/*`.
- `HTTP_API_KEY` still protects the real `/api/v1/expenses/text` endpoint even in local mode.
- In `http-dev` mode, Telegram, OpenAI, and YNAB credentials are not required.
- `DATABASE_PATH` is no longer part of the runtime baseline; keep it only if you need SQLite migration tooling.

## Docker Workflows

### Daily local dev

```bash
docker compose up app-dev
```

What this starts:

- the app on `http://localhost:8080`
- `APP_MODE=http-dev`
- `EXTERNAL_MODE=stub`
- PostgreSQL persistence using `POSTGRES_DSN`
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

Use different DSNs depending on where the client is running:

- From the host machine, use `127.0.0.1`:

```bash
export POSTGRES_DSN=postgresql://ynab:ynab@127.0.0.1:5432/ynab_bot
```

- From the `app-dev` Docker container, use the Compose service name `postgres`:

```env
POSTGRES_DSN=postgresql://ynab:ynab@postgres:5432/ynab_bot
```

If you want to run the local app itself against PostgreSQL, start both services together:

```bash
docker compose --profile postgres up
```

### Optional local pgAdmin

Use this when you want a local GUI to browse or edit the local PostgreSQL database.

Start pgAdmin together with PostgreSQL:

```bash
docker compose --profile admin up
```

This starts:

- PostgreSQL on `127.0.0.1:5432`
- pgAdmin on `http://127.0.0.1:5050`

pgAdmin persists its saved servers and settings in the named Docker volume `pgadmin-data`, so your local admin setup survives restarts.

Set or override these local credentials in `config/.env.dev` if needed:

```env
PGADMIN_DEFAULT_EMAIL=admin@local.dev
PGADMIN_DEFAULT_PASSWORD=change-me
```

Inside pgAdmin, register the local database with:

- Host: `postgres`
- Port: `5432`
- Username: `ynab`
- Password: `ynab`
- Database: `ynab_bot`

Use `postgres` as the hostname inside pgAdmin because it runs on the same Docker Compose network as the PostgreSQL service.

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

You can also import the committed Postman bundle from `docs/dev/postman/` and run the same flows interactively.

4. Run tests from the virtual environment:

```bash
.venv/bin/pytest
```

For the PostgreSQL integration smoke test specifically:

```bash
export POSTGRES_INTEGRATION_DSN=postgresql://ynab:ynab@127.0.0.1:5432/ynab_bot
.venv/bin/pytest tests/test_postgres_integration.py
```

For `app-dev`, set this in `config/.env.dev`:

```env
POSTGRES_DSN=postgresql://ynab:ynab@postgres:5432/ynab_bot
```

`127.0.0.1` works for commands you run directly on your machine. `postgres` is required for the app container because `127.0.0.1` inside Docker points back to the container itself, not the PostgreSQL service.

If you inspect the same database through pgAdmin, it should also use `postgres` as the hostname for the same reason.

To exercise the current SQLite-to-PostgreSQL migration scaffold locally:

```bash
.venv/bin/python scripts/dev/migrate_sqlite_to_postgres.py \
  --sqlite-path data/users.db \
  --postgres-dsn "$POSTGRES_DSN"
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

Also verify:

- the PostgreSQL container is running
- `POSTGRES_DSN` uses `postgres` as the hostname inside Docker Compose, not `127.0.0.1`

### pgAdmin cannot connect to PostgreSQL

If pgAdmin is running in Docker Compose, register the server with:

- Host: `postgres`
- Port: `5432`

Do not use `127.0.0.1` inside pgAdmin, because that points to the pgAdmin container itself.

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
