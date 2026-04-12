# Plan: Shared HTTP Request Validation

## Objective & Context
- **Status:** Completed
- **Source Spec:** `docs/specs/2026-04-11-shared-http-request-validation.md`
- **Goal:** Make the production and dev text-message HTTP routes use the same validated request contract.
- **Approach:** Add a shared Pydantic model and parser for the common text-message payload, then route both handlers through it while preserving current success semantics.

## Affected Components
- `src/presentation/http/` — shared request model/parser plus handler integration
- `tests/test_expense_api_handler.py` — preserve production validation and flow expectations
- `tests/test_dev_api_handler.py` — add regression coverage for invalid `force_commit` coercion

## Prerequisites (Manual)
- [ ] None

## Implementation Steps

### Group 1
#### [x] Step 1: Add shared validated text-message request parsing
- **Files:** `src/presentation/http/`
- **Action:** Introduce a shared Pydantic model and parser for `telegram_user_id`, `text`, and `force_commit`; keep JSON parsing and validation errors deterministic.
- **Tests:** `tests/test_expense_api_handler.py`, `tests/test_dev_api_handler.py`

### Group 2 (depends on: Group 1)
#### [x] Step 2: Route prod and dev handlers through the shared validator
- **Files:** `src/presentation/http/handlers/expense_api_handler.py`, `src/presentation/http/dev_api_handler.py`
- **Action:** Remove duplicate text-message request validation and the dev `bool(...)` coercion path; keep route behavior otherwise unchanged.
- **Tests:** `tests/test_expense_api_handler.py`, `tests/test_dev_api_handler.py`

## Constraints & Architecture
- Shared validation is only for the common text-message request.
- No payload field renames or route changes.
- Invalid `force_commit` types must be rejected consistently in both handlers.

## Verification
- [x] Run `.venv/bin/pytest tests/test_expense_api_handler.py tests/test_dev_api_handler.py tests/test_http_server.py`
