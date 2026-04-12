# Plan: Constant-Time HTTP Auth

## Objective & Context
- **Status:** Completed
- **Source Spec:** `docs/specs/2026-04-11-constant-time-http-auth.md`
- **Goal:** Harden bearer-token verification without changing handler semantics.
- **Approach:** Replace string equality in `validate_bearer_token()` with `hmac.compare_digest()` and verify that auth-facing behavior remains unchanged.

## Affected Components
- `src/presentation/http/auth.py` — constant-time token comparison
- `tests/test_http_auth.py` — preserve auth helper expectations
- `tests/test_expense_api_handler.py`, `tests/test_dev_api_handler.py` — keep auth integration coverage green

## Prerequisites (Manual)
- [ ] None

## Implementation Steps

### Group 1
#### [x] Step 1: Harden bearer token comparison
- **Files:** `src/presentation/http/auth.py`
- **Action:** Switch the token equality check to `hmac.compare_digest()` while preserving current error behavior.
- **Tests:** `tests/test_http_auth.py`, `tests/test_expense_api_handler.py`, `tests/test_dev_api_handler.py`

## Constraints & Architecture
- No auth contract or route behavior changes.
- Error codes and messages remain stable.

## Verification
- [x] Run `.venv/bin/pytest tests/test_http_auth.py tests/test_expense_api_handler.py tests/test_dev_api_handler.py`
