# Plan: Sensitive URL Log Redaction

## Objective & Context
- **Status:** Completed
- **Source Spec:** `docs/specs/2026-08-02-sensitive-url-log-redaction.md`
- **Harness Roadmap:** Ignore
- **Goal:** Prevent sensitive URL parameters, credentials, and bare Telegram bot tokens from being emitted in application or third-party HTTP client logs.
- **Approach:** Add central logging redaction in `infrastructure.logging_config`, lower noisy HTTP client logger levels, and verify with focused tests.

## Affected Components
- `src/infrastructure/logging_config.py` — central redaction helpers, logging filter, formatter integration, third-party logger levels.
- `main.py` — direct startup error print redaction.
- `tests/infrastructure/test_logging_config.py` — redaction and `httpx` logger configuration coverage.
- `tests/infrastructure/test_main.py` — startup error stdout redaction coverage.

## Prerequisites (Manual)
- [x] None.

## Implementation Steps
*(Models MUST mark steps with [x] as they are completed and save the file)*

### Group 1

#### [x] Step 1: Add Central Log Redaction
- **Role:** Step Implementer
- **Files:** `src/infrastructure/logging_config.py`, `main.py`, `tests/infrastructure/test_logging_config.py`, `tests/infrastructure/test_main.py`
- **Write Scope:** `src/infrastructure/logging_config.py`, `main.py`, `tests/infrastructure/test_logging_config.py`, `tests/infrastructure/test_main.py`
- **Read Scope:** `docs/specs/2026-08-02-sensitive-url-log-redaction.md`, `src/infrastructure/logging_config.py`, `main.py`, `tests/infrastructure/test_logging_config.py`, `tests/infrastructure/test_main.py`
- **Depends On:** None
- **Auto-Delegable:** no
- **Escalation Target:** Debugger
- **Action:** Add reusable redaction helpers/filter, attach the filter to configured handlers, ensure formatters apply redaction, route direct startup error printing through the same redactor, and add tests for JSON/human logs, log args, structured extras, bearer credentials, Telegram bot URL path tokens, bare Telegram bot tokens in exception messages, exception traceback text, startup stdout, and `httpx` logger levels.
- **Verification:** `.venv/bin/pytest tests/infrastructure/test_main.py tests/infrastructure/test_logging_config.py -q` (`39 passed`)

### Group 2 (depends on: Group 1)

#### [x] Step 2: Review and Close Out
- **Role:** Code Reviewer
- **Files:** `src/infrastructure/logging_config.py`, `tests/infrastructure/test_logging_config.py`, `docs/specs/2026-08-02-sensitive-url-log-redaction.md`, `docs/plans/2026-08-02-sensitive-url-log-redaction.md`
- **Write Scope:** `docs/plans/2026-08-02-sensitive-url-log-redaction.md`, `docs/specs/archive/2026-08-02-sensitive-url-log-redaction.md`, `docs/plans/archive/2026-08-02-sensitive-url-log-redaction.md`, `docs/wip_state.md`
- **Read Scope:** Modified files, `docs/ARCHITECTURE.md`
- **Depends On:** Group 1
- **Auto-Delegable:** no
- **Escalation Target:** User
- **Action:** Review diff against the spec, run targeted verification, archive completed SPEC/PLAN if review passes, and update handoff state.
- **Verification:** `.venv/bin/pytest tests/infrastructure/test_logging_config.py -q`

## Constraints & Architecture
- Use the existing Python logging module and formatter structure.
- Preserve existing structured fields and log formats.
- No database, YNAB milliunit, or repository factory changes.

## Verification
- [x] `.venv/bin/pytest tests/infrastructure/test_logging_config.py -q`
- [x] `.venv/bin/python scripts/harness/check_docs.py`
- [x] `.venv/bin/pytest`
