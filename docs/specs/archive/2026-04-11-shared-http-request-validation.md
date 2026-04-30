# Spec: Shared HTTP Request Validation

## Metadata
- **Status:** Implemented
- **Harness Roadmap Marker:** E.13
- **Owner:** Codex
- **Related Roadmap Item:** None
- **Related ADRs:** None

## Summary
The production HTTP expense endpoint and the dev HTTP message harness currently validate the same text-message payload differently. This change introduces one shared validated request contract for the common `telegram_user_id`, `text`, and `force_commit` payload so both entry points accept and reject the same inputs. The goal is consistent request behavior without changing route names or field names.

## Problem
- The production endpoint validates `force_commit` as a real boolean.
- The dev harness coerces `force_commit` with `bool(...)`, so values like `"false"` or `1` become `True`.
- The same payload shape behaves differently depending on the route.

## Goals
- Use one shared validated request model for text-message HTTP requests.
- Make dev and production validation behavior consistent.
- Reject invalid boolean and field types deterministically.
- Preserve current request field names and successful flows.

## Non-Goals
- Refactoring dev bootstrap request validation.
- Changing endpoint paths or payload field names.
- Introducing broader API versioning changes.

## Users / Consumers
- External callers of `POST /api/v1/expenses/text`
- Local developers using `/dev/messages/text`

## Expected Behavior
- Both text-message endpoints parse the same JSON body contract.
- `force_commit` must be a real boolean in both environments.
- Invalid JSON still maps to a request-format error.
- Invalid field types still map to a request-validation error.

## Inputs and Outputs
- **Inputs:** JSON request body with `telegram_user_id`, `text`, optional `force_commit`
- **Outputs:** Validated in-memory request object or deterministic validation error
- **Public Interfaces:** `POST /api/v1/expenses/text`, `POST /dev/messages/text`

## Business Rules and Constraints
- Shared validation applies only to the common text-message request contract.
- Field names remain unchanged.
- Successful request behavior must remain unchanged.

## Edge Cases and Failure Handling
- Non-object JSON payloads must be rejected.
- Blank `text` must be rejected.
- `telegram_user_id` booleans must not be accepted as integers.
- `force_commit` strings and numeric values must be rejected.

## Acceptance Criteria
- [ ] Production and dev text-message routes accept the same valid payloads.
- [ ] Production and dev text-message routes reject `"false"`, `1`, and similar invalid `force_commit` values.
- [ ] Existing successful expense and query simulation flows remain intact.

## Open Questions
- None

## References
- `src/presentation/http/handlers/expense_api_handler.py`
- `src/presentation/http/dev_api_handler.py`
- `requirements.txt`
