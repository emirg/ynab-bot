#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys

from project_bootstrap import ensure_src_path

ensure_src_path()

from infrastructure.repositories.postgres_manager import PostgresDatabaseManager
from infrastructure.repositories.sqlite_to_postgres_migrator import SQLiteToPostgresMigrator


def main() -> int:
    parser = argparse.ArgumentParser(description="Migrate local SQLite persistence into PostgreSQL.")
    parser.add_argument("--sqlite-path", required=True, help="Path to the SQLite database file.")
    parser.add_argument("--postgres-dsn", required=True, help="PostgreSQL DSN for the destination database.")
    args = parser.parse_args()

    migrator = SQLiteToPostgresMigrator(
        sqlite_path=args.sqlite_path,
        postgres_manager=PostgresDatabaseManager(args.postgres_dsn),
    )
    summary = migrator.migrate()

    print("SQLite to PostgreSQL migration completed.")
    print(f"Total rows copied: {summary.total_rows}")
    for table_name, count in summary.copied_rows_by_table.items():
        print(f"- {table_name}: {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
