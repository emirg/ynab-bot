# Plan: Milestone 2.1 -- Configuracion de Split

## Objective & Context
- **Status:** COMPLETED (archived 2026-03-14). Review notes: 3 bugs found (missing imports in bot.py, callback routing collision split_rm_ vs split_rma_, import convention in split_config_repository.py). See review summary for details.
- **Harness Roadmap:** Ignore
- **Goal:** Implement the `/splitwise` command and its full configuration flow so users can persist which YNAB categories represent Splitwise groups, associate person aliases to each group, and designate a single "Shared Transactions" YNAB account -- all via inline keyboards.
- **Why:** This is the data foundation for Milestones 2.2 (intent detection) and 2.3 (split transaction creation). Without persisted split configuration, the bot cannot know where to route shared expenses.

## Prerequisites (Manual)
- [ ] None. No new env vars, API keys, or infrastructure changes required.

## Design Decisions (Agreed)

1. **UX pattern:** Inline keyboard panel (matches existing `ConfigHandler`/`/config` pattern). No `ConversationHandler`.
2. **Group label:** Each Splitwise category entry stores a `label` equal to the YNAB category name (e.g., "Gastos Compartidos").
3. **Person aliases:** Stored explicitly alongside the group config. Example: group "Gastos Compartidos" has aliases `["Juan", "Juancho"]`. Used later by the LLM parser to route "con Juan" to the correct group.
4. **Shared Transactions account:** One per user (not per person). Stored separately from split groups.
5. **Default ratio:** Global 50/50. Not stored per group. Per-message ratios are deferred to 2.2/2.3.
6. **Scope:** Configuration only. No changes to `ExpenseService`, `LLMExpenseParser`, or `Expense` model.
7. **Guard:** `/splitwise` requires authentication + configured budget (needs YNAB category/account data).

## DB Schema (Migration v5)

```sql
-- Table 1: split_groups (one row per Splitwise category per user)
CREATE TABLE IF NOT EXISTS split_groups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id INTEGER NOT NULL,
    category_id TEXT NOT NULL,
    category_name TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(telegram_id, category_id),
    FOREIGN KEY (telegram_id) REFERENCES user_configurations(telegram_id)
);

-- Table 2: split_person_aliases (person names that map to a split group)
CREATE TABLE IF NOT EXISTS split_person_aliases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    split_group_id INTEGER NOT NULL,
    alias TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(split_group_id, alias),
    FOREIGN KEY (split_group_id) REFERENCES split_groups(id) ON DELETE CASCADE
);

-- Table 3: split_shared_account (one row per user, stores shared account config)
CREATE TABLE IF NOT EXISTS split_shared_account (
    telegram_id INTEGER PRIMARY KEY,
    account_id TEXT NOT NULL,
    account_name TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (telegram_id) REFERENCES user_configurations(telegram_id)
);

CREATE INDEX IF NOT EXISTS idx_split_groups_user ON split_groups(telegram_id);
CREATE INDEX IF NOT EXISTS idx_split_aliases_group ON split_person_aliases(split_group_id);
```

## Implementation Steps
*(Models MUST mark steps with [x] as they are completed and save the file)*

### [x] Step 1: Domain Model -- `SplitGroup` and `SharedAccountConfig`
### [x] Step 2: Repository Interface -- `SplitConfigRepository`
### [x] Step 3: DB Migration v5
### [x] Step 4: SQLite Implementation -- `SQLiteSplitConfigRepository`
### [x] Step 5: Application Service -- `SplitConfigService`
### [x] Step 6: Formatter -- `SplitConfigResponseFormatter`
### [x] Step 7: Keyboards -- Split config keyboard builders
### [x] Step 8: Handler -- `SplitConfigHandler`
### [x] Step 9: Wire into DI Container
### [x] Step 10: Register Handlers in `bot.py`
### [x] Step 11: Update `/help` and `/config` Messages
### [x] Step 12: Add conftest Fixtures for Split Config

## Post-Review Bugs (to fix before 2.2)

### BUG 1 (CRITICAL): Missing imports in `bot.py`
`handle_text_dispatch` uses `Update` and `ContextTypes` type hints but neither is imported. Runtime crash on bot startup.
**Fix:** Add `from telegram import Update` and `ContextTypes` to imports.

### BUG 2 (MODERATE): Callback routing collision `split_rm_` vs `split_rma_`
In `handle_callback_query`, `data.startswith("split_rm_")` catches alias removal callbacks (`split_rma_...`) before the `split_rma_` branch. Alias removal buttons trigger group removal instead.
**Fix:** Reorder checks or rename group removal prefix to `split_rmg_`.

### BUG 3 (MODERATE): Import convention violation in `split_config_repository.py`
Uses `from src.domain.models...` instead of `from domain.models...`. Inconsistent with all other source files.
**Fix:** Remove `src.` prefix.
