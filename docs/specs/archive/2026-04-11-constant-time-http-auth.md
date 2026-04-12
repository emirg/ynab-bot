# Spec: Constant-Time HTTP Auth

## Metadata
- **Status:** Implemented
- **Owner:** Codex
- **Related Roadmap Item:** None
- **Related ADRs:** None

## Summary
HTTP bearer-token validation currently compares the provided token with the expected token using normal string equality. This hardening change switches the comparison primitive to constant-time comparison while preserving the current auth contract, error codes, and handler behavior. The goal is targeted security improvement without any broader auth redesign.

## Problem
- Bearer token validation uses standard string equality.
- A constant-time comparison primitive is a safer default for secret comparison.

## Goals
- Use constant-time comparison for the bearer token value.
- Preserve current auth behavior and exceptions.
- Keep the change local to the HTTP auth helper.

## Non-Goals
- Redesigning HTTP authentication.
- Changing auth headers, routes, or error codes.
- Introducing session or OAuth-based API auth.

## Users / Consumers
- Production HTTP expense endpoint
- Dev HTTP harness

## Expected Behavior
- Missing header, invalid scheme, invalid token, and valid token cases behave exactly as before from the caller perspective.
- The token equality check uses a constant-time comparison primitive.

## Inputs and Outputs
- **Inputs:** HTTP `Authorization` header, expected bearer token
- **Outputs:** Boolean success or `HTTPAuthError`
- **Public Interfaces:** `validate_bearer_token()`

## Business Rules and Constraints
- Keep current error codes and messages stable.
- Do not alter route-level auth behavior.

## Edge Cases and Failure Handling
- Missing header and invalid scheme handling remain unchanged.
- Invalid token still raises the same auth error.

## Acceptance Criteria
- [ ] The token check uses constant-time comparison.
- [ ] Existing auth behavior remains unchanged.
- [ ] Auth integration tests continue to pass.

## Open Questions
- None

## References
- `src/presentation/http/auth.py`
- `tests/test_http_auth.py`
