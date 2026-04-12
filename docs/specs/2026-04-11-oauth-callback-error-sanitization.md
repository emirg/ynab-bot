# Spec: OAuth Callback Error Sanitization

## Metadata
- **Status:** Implemented
- **Owner:** Codex
- **Related Roadmap Item:** None
- **Related ADRs:** None

## Summary
The OAuth callback currently renders raw exception text into HTML responses, which can leak internal details and reflect unsafe content back to the browser. This hardening change replaces raw exception rendering with fixed Spanish user-facing messages while keeping detailed diagnostics in logs. The result is a safer and more consistent callback experience.

## Problem
- Browser responses for OAuth callback failures currently interpolate `str(exception)` directly into HTML.
- Raw exception text can expose internal implementation details.
- Unsafe exception text can become reflected HTML content.
- The callback pages currently return user-facing text in English, violating the project UI language invariant.

## Goals
- Stop reflecting raw exception text into browser HTML.
- Return stable, user-safe Spanish callback pages.
- Preserve detailed failure context in logs.
- Keep current routing and OAuth flow behavior unchanged aside from safe messaging.

## Non-Goals
- Redesigning OAuth state handling or token exchange behavior.
- Changing Telegram post-OAuth notifications.
- Introducing a new web framework or templating layer.

## Users / Consumers
- End users connecting their YNAB account through the browser callback.
- Maintainers debugging OAuth failures via logs.

## Expected Behavior
- Missing or invalid callback parameters return a safe Spanish HTML error page.
- Unavailable OAuth service returns a safe Spanish HTML error page.
- Token exchange failures return a generic Spanish error page without exposing internal exception details.
- Success pages remain user-friendly and browser-safe.
- Logs retain the underlying technical error details for debugging.

## Inputs and Outputs
- **Inputs:** Browser GET requests to `/oauth/callback`, missing query params, token exchange exceptions.
- **Outputs:** Sanitized HTML success/error pages, structured log entries with technical context.
- **Public Interfaces:** Browser-visible behavior of `/oauth/callback`.

## Business Rules and Constraints
- No raw exception text may be rendered to the browser.
- Any interpolated HTML content must be escaped.
- User-facing callback strings must be in Spanish.
- Existing HTTP status semantics should remain unless a concrete safety reason requires change.

## Edge Cases and Failure Handling
- Missing `code` or `state` must show a fixed user-safe error.
- If the OAuth service is unavailable, the page must remain safe and actionable.
- If the post-success callback fails, the browser should still receive the success page while the error is logged.

## Acceptance Criteria
- [ ] Browser error pages do not contain raw exception text from OAuth failures.
- [ ] Callback success and error pages use Spanish user-facing copy.
- [ ] Tests include a regression that an unsafe exception string is not reflected into HTML.
- [ ] Existing OAuth callback flow and status codes remain intact.

## Open Questions
- None

## References
- `docs/AI_WORKFLOW.md`
- `src/infrastructure/health.py`
- `tests/test_health.py`
