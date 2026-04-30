# Plan: Temporarily Disable /resumen

## Objective & Context
- **Status:** Completed
- **Harness Roadmap Marker:** E.16
- **Source Spec:** `docs/specs/archive/2026-04-16-disable-resumen-temporarily.md`
- **Goal:** Disable `/resumen` responses immediately with a clear temporary message and stop advertising the command in user-facing help.
- **Approach:** Keep the existing command registration in place, short-circuit the Telegram handler to a fixed response, and update tests/help text to match the new temporary rollback behavior.

## Affected Components
- `src/presentation/telegram/handlers/summary_handler.py` — short-circuit `/resumen` to a fixed disabled message
- `src/presentation/telegram/formatters.py` — remove `/resumen` from the visible command list
- `tests/presentation/telegram/test_summary_handler.py` — replace active-summary expectations with disabled-command coverage

## Prerequisites (Manual)
- [x] None

## Implementation Steps
*(Models MUST mark steps with [x] as they are completed and save the file)*

### Group 1

#### [x] Step 1: Disable Handler Execution
- **Files:** `src/presentation/telegram/handlers/summary_handler.py`
- **Action:** Replace the `/resumen` execution path with a fixed Spanish temporary-disabled message and avoid invoking summary parsing or generation.
- **Tests:** `tests/presentation/telegram/test_summary_handler.py` — assert disabled response and no service calls

### Group 2 (depends on: Group 1)

#### [x] Step 2: Remove Help Advertising
- **Files:** `src/presentation/telegram/formatters.py`
- **Action:** Remove `/resumen` from the command list so the bot stops advertising a disabled feature.
- **Tests:** No dedicated test file; covered by manual verification of formatter output if needed.

#### [x] Step 3: Rewrite Summary Handler Tests
- **Files:** `tests/presentation/telegram/test_summary_handler.py`
- **Action:** Replace the existing summary-generation expectations with temporary-disable behavior and preserve minimal delegation coverage for the handler entrypoint.
- **Tests:** `tests/presentation/telegram/test_summary_handler.py`

## Constraints & Architecture
- User-facing strings must remain in Spanish.
- Keep `/resumen` registered so users receive an explicit explanation instead of an unknown-command failure.
- Do not remove unrelated callback wiring or revert unrelated summary implementation code.

## Verification
- [x] Run `.venv/bin/pytest tests/presentation/telegram/test_summary_handler.py`
- [x] Confirm `/resumen` no longer appears in `GeneralResponseFormatter.format_command_list()`
