# Spec: Typed Prepared Expense Flow

## Metadata
- **Status:** Implemented
- **Harness Roadmap Marker:** E.13
- **Owner:** Codex
- **Related Roadmap Item:** None
- **Related ADRs:** `docs/adrs/2026-04-11-prepared-expense-domain-contract.md`

## Summary
The two-phase expense flow currently passes around untyped dictionaries between the service layer, HTTP handlers, Telegram confirmation flow, and tests. This refactor introduces a dedicated typed `PreparedExpense` contract so the prepare/commit boundary is explicit and stable. The goal is better maintainability and less key-based duplication without changing expense behavior.

## Problem
- `prepare_expense`, `prepare_shared_expense`, and `prepare_receipt` return raw dicts.
- `commit_shared_expense`, HTTP handlers, Telegram confirmation logic, and tests index those dicts by string keys.
- The workflow boundary exists conceptually but is not represented as a type.

## Goals
- Replace the raw prepared-expense dict contract with a typed object.
- Keep current prepare/preview/commit behavior unchanged.
- Reduce duplication and fragile string-key access in handlers and tests.
- Make the two-phase boundary explicit for future maintenance.

## Non-Goals
- Redesigning the overall expense-processing workflow.
- Changing persisted schema or external API payloads.
- Replacing existing domain dataclasses with Pydantic models.

## Users / Consumers
- `ExpenseService`
- HTTP handlers using the preview/commit flow
- Telegram confirmation flow
- Tests that construct or assert prepared-expense values

## Expected Behavior
- Prepare methods return a typed `PreparedExpense`.
- Commit logic consumes `PreparedExpense` rather than a raw dict.
- Telegram confirmation state still supports preview and confirm flows for text, voice, and receipt inputs.
- HTTP preview and commit responses continue to work for regular and shared expenses.

## Inputs and Outputs
- **Inputs:** Parsed expense intent, user configuration, built `Expense`, preview state
- **Outputs:** `PreparedExpense` object, committed `ExpenseResult`, preview responses
- **Public Interfaces:** Internal prepare/commit method contracts across service and presentation layers

## Business Rules and Constraints
- The typed contract belongs in the domain model layer.
- Existing prepare/commit behavior must not change.
- The object must carry all data currently required by HTTP and Telegram preview/commit flows.

## Edge Cases and Failure Handling
- Shared expenses must still carry split-specific data through the typed object.
- Receipt preparation must use the same typed contract as text preparation.
- Confirmation callbacks must still handle stale pending state safely.

## Acceptance Criteria
- [ ] All prepare methods return `PreparedExpense`.
- [ ] Shared and regular commit paths consume the typed object without raw dict indexing.
- [ ] HTTP and Telegram preview/commit tests pass with the new typed contract.
- [ ] Tests stop using raw prepared dicts as the primary transport contract.

## Open Questions
- None

## References
- `src/application/services/expense_service.py`
- `src/presentation/http/handlers/expense_api_handler.py`
- `src/presentation/telegram/handlers/expense_handler.py`
