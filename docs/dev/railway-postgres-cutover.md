# Railway PostgreSQL Cutover

This runbook describes the intended production migration from the legacy SQLite runtime to PostgreSQL on Railway.

## Goal

Migrate production persistence to PostgreSQL without wiping current data.

The migration order is:

1. freeze writes
2. back up the current SQLite database
3. copy data into PostgreSQL
4. validate copied data
5. switch runtime to PostgreSQL
6. keep the SQLite backup for rollback during stabilization

## Data Policy

- Current data should be preserved.
- A database wipe is not the intended migration path.
- The only safe destructive retry would be recreating the target PostgreSQL database before cutover, not deleting the SQLite source.

## Production Source of Truth

The old production data lives in the SQLite file on the Railway-mounted `/data` volume.

In this project, the runtime source path was:

```env
DATABASE_PATH=/data/users.db
```

That file contains:

- `user_configurations`
- `payee_category_mappings`
- `user_corrections`
- `recent_transactions`
- `split_groups`
- `split_person_aliases`
- `split_shared_account`

## Backup Procedure

Before migration, create a SQLite backup from the production database file.

Example from a Railway shell:

```bash
python - <<'PY'
import os
import sqlite3
from datetime import datetime

source = os.environ.get("DATABASE_PATH", "/data/users.db")
timestamp = datetime.utcnow().strftime("%Y-%m-%d-%H%M%S")
target = f"/data/pre-postgres-cutover-{timestamp}.db"

src = sqlite3.connect(source)
dst = sqlite3.connect(target)
with dst:
    src.backup(dst)
src.close()
dst.close()

print(f"Backup created: {target}")
PY
```

Verify the artifact:

```bash
ls -lh /data/pre-postgres-cutover-*.db
sha256sum /data/pre-postgres-cutover-*.db
```

## Migration Command

Once PostgreSQL is provisioned and `POSTGRES_DSN` is available, run:

```bash
PYTHONPATH=/app python scripts/dev/migrate_sqlite_to_postgres.py \
  --sqlite-path /data/pre-postgres-cutover-YYYY-MM-DD-HHMMSS.db \
  --postgres-dsn "$POSTGRES_DSN"
```

This script:

- initializes the PostgreSQL schema
- copies all supported tables from SQLite
- preserves upsert semantics on the destination
- resets PostgreSQL sequences after copy

## Validation

After migration, validate:

- row counts across all copied tables
- at least one real user configuration row
- learning data presence
- split configuration rows
- application smoke checks through Telegram and HTTP

## Runtime Cutover

After validation passes:

1. deploy the PostgreSQL-capable app version
2. set `POSTGRES_DSN` on the Railway app service
3. ensure the app runs on the PostgreSQL runtime path
4. run health, Telegram, and authenticated HTTP smoke checks

## Rollback

Rollback uses the preserved SQLite backup.

If PostgreSQL cutover fails after deployment:

1. stop the PostgreSQL-backed runtime
2. restore the previous runtime configuration
3. point the app back to the SQLite source
4. redeploy the last known-good release

Important limitation:

- writes accepted only by PostgreSQL after cutover are not automatically replayed into SQLite

Because of that, rollback is safest immediately after cutover, before significant new write traffic accumulates.

## Current Outcome

Phase 1 production cutover completed with:

- SQLite backup created from `/data/users.db`
- migration completed successfully into PostgreSQL
- runtime switched to PostgreSQL
- health check, Telegram flows, and authenticated HTTP expense flow validated in production

The SQLite backup should still be retained through the stabilization window before removing rollback artifacts.
