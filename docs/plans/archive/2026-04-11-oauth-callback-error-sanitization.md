# Plan: OAuth Callback Error Sanitization

## Objective & Context
- **Status:** Completed
- **Harness Roadmap Marker:** E.13
- **Source Spec:** `docs/specs/2026-04-11-oauth-callback-error-sanitization.md`
- **Goal:** Prevent raw OAuth exception text from being rendered into browser HTML and align callback pages with the Spanish UI invariant.
- **Approach:** Centralize safe HTML rendering in `infrastructure.health`, replace raw exception interpolation with fixed Spanish messages, and tighten the callback regression tests.

## Affected Components
- `src/infrastructure/health.py` — sanitize callback HTML responses and keep detailed logging
- `tests/test_health.py` — update callback assertions and add non-reflection regression coverage

## Prerequisites (Manual)
- [x] None

## Implementation Steps

### Group 1
<!-- Harden the callback response path -->

#### [x] Step 1: Sanitize OAuth callback HTML responses
- **Files:** `src/infrastructure/health.py`
- **Action:** Replace raw exception interpolation with fixed Spanish user-facing messages, centralize safe error-page rendering, and keep technical error details in logs only.
- **Tests:** `tests/test_health.py` — update callback tests to assert safe Spanish messaging and absence of reflected exception content.

## Constraints & Architecture
- Do not change the OAuth flow or public callback route.
- Do not expose technical exception strings in HTML responses.
- Preserve current status-code behavior unless a safety issue appears during implementation.
- Keep user-facing strings in Spanish.

## Verification
- [x] Run `.venv/bin/pytest tests/test_health.py tests/test_main.py`
- [x] Run `.venv/bin/pytest tests/test_http_server.py`
