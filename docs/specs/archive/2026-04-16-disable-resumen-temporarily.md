# Spec: Temporarily Disable /resumen

## Metadata
- **Status:** Implemented
- **Owner:** Codex
- **Related Roadmap Item:** `/resumen` on-demand spending summary
- **Related ADRs:** None

## Summary
The `/resumen` command currently produces results that still diverge from YNAB Reflect. Until that discrepancy is resolved, the bot should stop serving summary data through `/resumen` and instead return a clear temporary-disabled message in Spanish. This prevents users from acting on inconsistent information while preserving an explicit response path for the command.

## Problem
- `/resumen` output is still inconsistent with YNAB Reflect.
- Keeping the feature active risks presenting users with misleading financial summaries.

## Goals
- Disable `/resumen` immediately without breaking bot command routing.
- Tell users clearly that `/resumen` is temporarily unavailable.
- Stop advertising `/resumen` in the visible command list while it is disabled.

## Non-Goals
- Fix the underlying summary logic differences with YNAB Reflect.
- Remove the `/resumen` handler wiring entirely from the bot.

## Users / Consumers
- Telegram users who invoke `/resumen`
- Maintainers who need a reversible temporary rollback

## Expected Behavior
- Any `/resumen` invocation returns a short Spanish message explaining that the feature is temporarily disabled and may return later.
- The handler does not compute or fetch summary data while disabled.
- `/help` / command list output no longer advertises `/resumen`.

## Inputs and Outputs
- **Inputs:** `/resumen`, `/resumen dia`, `/resumen semana`, `/resumen mes`
- **Outputs:** One temporary-disabled Telegram message
- **Public Interfaces:** `/resumen`, help/command list formatting

## Business Rules and Constraints
- User-facing copy must remain in Spanish.
- The rollback should be small and easy to reverse later.
- No YNAB summary computation should run for disabled `/resumen` requests.

## Edge Cases and Failure Handling
- Existing `/resumen` arguments are ignored while the feature is disabled.
- The temporary-disabled response should be returned even if the user provides an otherwise valid period argument.

## Acceptance Criteria
- [x] `/resumen` always returns the temporary-disabled message.
- [x] The summary service is not called from the disabled handler path.
- [x] The command list no longer presents `/resumen` as an available query command.

## Open Questions
- None

## References
- `src/presentation/telegram/handlers/summary_handler.py`
- `src/presentation/telegram/formatters.py`
