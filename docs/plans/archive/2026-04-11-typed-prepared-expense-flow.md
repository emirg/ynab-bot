# Plan: Typed Prepared Expense Flow

## Objective & Context
- **Status:** Completed
- **Source Spec:** `docs/specs/2026-04-11-typed-prepared-expense-flow.md`
- **Goal:** Replace the raw prepared-expense dict transport with a typed domain contract.
- **Approach:** Add a `PreparedExpense` dataclass to the domain model set, refactor prepare/commit service methods and handlers to use it, and update tests to construct the typed object.

## Affected Components
- `src/domain/models/expense.py` and `src/application/services/expense_service.py` — define and return the typed prepared-expense contract
- `src/presentation/http/handlers/expense_api_handler.py` and `src/presentation/telegram/handlers/expense_handler.py` — consume the typed contract in preview/commit flows
- `tests/test_expense_service.py`, `tests/test_expense_api_handler.py`, `tests/test_expense_handler.py` — migrate helpers and assertions to the typed object

## Prerequisites (Manual)
- [ ] None

## Implementation Steps

### Group 1
#### [x] Step 1: Introduce the typed domain contract
- **Files:** `src/domain/models/expense.py`
- **Action:** Add a `PreparedExpense` dataclass carrying the prepare-phase fields currently moved through raw dicts.
- **Tests:** `tests/test_expense_service.py`

### Group 2 (depends on: Group 1)
#### [x] Step 2: Refactor prepare/commit service methods to use PreparedExpense
- **Files:** `src/application/services/expense_service.py`
- **Action:** Return `PreparedExpense` from prepare methods and accept it in shared commit paths while preserving behavior.
- **Tests:** `tests/test_expense_service.py`

### Group 3 (depends on: Group 2)
#### [x] Step 3: Update presentation-layer preview and confirmation flows
- **Files:** `src/presentation/http/handlers/expense_api_handler.py`, `src/presentation/telegram/handlers/expense_handler.py`
- **Action:** Replace prepared-dict indexing with typed attribute access in HTTP preview/commit and Telegram confirmation flows.
- **Tests:** `tests/test_expense_api_handler.py`, `tests/test_expense_handler.py`

## Constraints & Architecture
- `PreparedExpense` is a domain dataclass, not a Pydantic model.
- No external API wire-shape changes.
- Keep text, shared-expense, voice, and receipt confirmation flows working.
- This plan follows ADR `docs/adrs/2026-04-11-prepared-expense-domain-contract.md`.

## Verification
- [x] Run `.venv/bin/pytest tests/test_expense_service.py tests/test_expense_api_handler.py tests/test_expense_handler.py`
