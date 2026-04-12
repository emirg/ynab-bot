from __future__ import annotations

POSTGRES_MIGRATIONS = [
    (
        1,
        "Create PostgreSQL baseline schema from SQLite v9",
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            description TEXT NOT NULL,
            applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );

        CREATE TABLE IF NOT EXISTS user_configurations (
            telegram_id BIGINT PRIMARY KEY,
            status TEXT DEFAULT 'pending',
            budget_id TEXT,
            default_account_id TEXT,
            default_account_name TEXT,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW(),
            approved_at TIMESTAMPTZ,
            approved_by BIGINT,
            ynab_access_token TEXT,
            ynab_refresh_token TEXT,
            ynab_token_expires_at TIMESTAMPTZ,
            timezone TEXT DEFAULT 'America/Bogota',
            last_weekly_summary_sent TIMESTAMPTZ,
            confirm_before_create BOOLEAN DEFAULT FALSE
        );

        CREATE TABLE IF NOT EXISTS payee_category_mappings (
            id BIGSERIAL PRIMARY KEY,
            telegram_id BIGINT NOT NULL REFERENCES user_configurations(telegram_id) ON DELETE CASCADE,
            normalized_payee TEXT NOT NULL,
            category_id TEXT NOT NULL,
            category_name TEXT NOT NULL DEFAULT '',
            count INTEGER NOT NULL DEFAULT 1,
            last_updated TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE(telegram_id, normalized_payee, category_id)
        );

        CREATE TABLE IF NOT EXISTS user_corrections (
            id BIGSERIAL PRIMARY KEY,
            telegram_id BIGINT NOT NULL REFERENCES user_configurations(telegram_id) ON DELETE CASCADE,
            normalized_payee TEXT NOT NULL,
            old_category_id TEXT NOT NULL,
            new_category_id TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );

        CREATE TABLE IF NOT EXISTS recent_transactions (
            id BIGSERIAL PRIMARY KEY,
            telegram_id BIGINT NOT NULL REFERENCES user_configurations(telegram_id) ON DELETE CASCADE,
            payee TEXT NOT NULL,
            amount DOUBLE PRECISION NOT NULL,
            category_id TEXT,
            category_name TEXT,
            confidence DOUBLE PRECISION DEFAULT 0.0,
            parser_source TEXT DEFAULT 'unknown',
            ynab_transaction_id TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );

        CREATE TABLE IF NOT EXISTS split_groups (
            id BIGSERIAL PRIMARY KEY,
            telegram_id BIGINT NOT NULL REFERENCES user_configurations(telegram_id) ON DELETE CASCADE,
            category_id TEXT NOT NULL,
            category_name TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE(telegram_id, category_id)
        );

        CREATE TABLE IF NOT EXISTS split_person_aliases (
            id BIGSERIAL PRIMARY KEY,
            split_group_id BIGINT NOT NULL REFERENCES split_groups(id) ON DELETE CASCADE,
            alias TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE(split_group_id, alias)
        );

        CREATE TABLE IF NOT EXISTS split_shared_account (
            telegram_id BIGINT PRIMARY KEY REFERENCES user_configurations(telegram_id) ON DELETE CASCADE,
            account_id TEXT NOT NULL,
            account_name TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );

        CREATE INDEX IF NOT EXISTS idx_pcm_user_payee
            ON payee_category_mappings(telegram_id, normalized_payee);
        CREATE INDEX IF NOT EXISTS idx_recent_user
            ON recent_transactions(telegram_id, id DESC);
        CREATE INDEX IF NOT EXISTS idx_split_groups_user
            ON split_groups(telegram_id);
        CREATE INDEX IF NOT EXISTS idx_split_aliases_group
            ON split_person_aliases(split_group_id);
        """,
    ),
    (
        2,
        "Add advisor launch token and session tables",
        """
        CREATE TABLE IF NOT EXISTS advisor_launch_tokens (
            token_hash TEXT PRIMARY KEY,
            telegram_id BIGINT NOT NULL REFERENCES user_configurations(telegram_id) ON DELETE CASCADE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            expires_at TIMESTAMPTZ NOT NULL
        );

        CREATE TABLE IF NOT EXISTS advisor_sessions (
            token_hash TEXT PRIMARY KEY,
            telegram_id BIGINT NOT NULL REFERENCES user_configurations(telegram_id) ON DELETE CASCADE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            expires_at TIMESTAMPTZ NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_advisor_launch_tokens_expires
            ON advisor_launch_tokens(expires_at);
        CREATE INDEX IF NOT EXISTS idx_advisor_sessions_expires
            ON advisor_sessions(expires_at);
        """,
    ),
]
