# Spec: Sensitive URL Log Redaction

## Metadata
- **Status:** Implemented
- **Owner:** Codex
- **Related Roadmap Item:** None
- **Harness Roadmap:** Ignore
- **Related ADRs:** None

## Summary
Application logs must not expose bearer tokens, OAuth codes, API keys, or sensitive URL query parameters. Third-party HTTP clients such as `httpx` must not emit full request URLs during normal operation, and any URL-like value that reaches the project logging pipeline must be redacted before output.

## Problem
- `httpx` and related libraries can log request URLs that include advisor launch tokens, OAuth codes, or other sensitive query parameters.
- The logging formatter currently emits record messages and structured fields without sanitizing URL query values or bearer credentials.

## Goals
- Redact sensitive URL query parameters from JSON and human-readable logs.
- Redact bearer/basic credentials and known token-bearing URL path patterns.
- Redact bare Telegram Bot API token strings when a library includes the token directly in an exception message.
- Reduce `httpx`/`httpcore` request logging noise so full request URLs are not logged at INFO during normal operation.
- Cover the behavior with focused logging tests.

## Non-Goals
- Change HTTP request behavior or authentication semantics.
- Redact all identifiers such as user IDs, budget IDs, or transaction IDs.
- Introduce a new logging framework.

## Users / Consumers
- Operators reviewing Railway or local logs.
- Developers debugging the bot without exposing production secrets.

## Expected Behavior
- Logs containing URLs preserve scheme, host, path, and non-sensitive parameters while replacing sensitive parameter values with `[REDACTED]`.
- Logs containing bearer/basic credentials replace the credential value with `[REDACTED]`.
- Logs containing bare Telegram bot tokens replace the token value with `[REDACTED]`.
- `httpx` and `httpcore` loggers default to WARNING after logging setup.

## Inputs and Outputs
- **Inputs:** Python logging records, structured logging extras, URL strings, exception strings, third-party logger records.
- **Outputs:** JSON or human-readable log lines with sensitive values redacted.
- **Public Interfaces:** `infrastructure.logging_config.setup_logging`, `JsonFormatter`, `log_with_context`.

## Business Rules and Constraints
- Redaction must be applied centrally through the existing logging configuration.
- Existing JSON log fields must remain compatible.
- User-facing Spanish text behavior is unaffected.

## Edge Cases and Failure Handling
- URL values with repeated sensitive parameters must redact every sensitive value.
- Non-sensitive URL query parameters remain visible.
- Non-string log arguments must keep normal formatting unless redaction changes their rendered value.

## Acceptance Criteria
- [x] JSON logs redact `token`, `access_token`, `refresh_token`, `code`, `client_secret`, and `api_key` query values.
- [x] Human-readable logs redact the same sensitive URL parameters.
- [x] `Authorization: Bearer ...` and `Authorization: Basic ...` values are redacted in messages.
- [x] Bare Telegram Bot API tokens in exception messages are redacted.
- [x] `httpx` and `httpcore` loggers are configured at WARNING by default.
- [x] Existing logging tests continue to pass.

## Open Questions
- None.

## References
- `docs/AI_WORKFLOW.md`
- `docs/DOCUMENTATION_WORKFLOW.md`
