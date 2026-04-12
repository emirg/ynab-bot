# ADR: Use PreparedExpense As A Domain Contract

## Metadata
- **Status:** Accepted
- **Date:** 2026-04-11
- **Related Spec:** `docs/specs/2026-04-11-typed-prepared-expense-flow.md`
- **Related Plan:** `docs/plans/archive/2026-04-11-typed-prepared-expense-flow.md`
- **Supersedes:** None
- **Superseded By:** None

## Context
The prepare/commit expense flow is already a stable internal workflow shared by application services, HTTP handlers, Telegram confirmation logic, and tests. Today that boundary is expressed as raw dictionaries, which creates string-key duplication and hides the real contract. The project already uses domain dataclasses broadly, so the missing piece is an explicit typed model for the prepared-expense state.

## Decision
Introduce `PreparedExpense` as a domain-layer dataclass. Prepare methods will return it, and downstream preview/commit flows will consume it directly. Pydantic will be used for HTTP request validation, not for this internal workflow transport.

## Alternatives Considered
- **Option A:** Keep raw dicts.
  Rejected because it preserves the exact duplication and weak typing that prompted the refactor.
- **Option B:** Use a Pydantic model everywhere.
  Rejected because the boundary is internal workflow state, and the codebase already models similar internal concepts with dataclasses.
- **Option C:** Keep the type private to the service layer.
  Rejected because the contract is shared across service and presentation layers and should be explicit at a common boundary.

## Consequences
- **Positive:** The prepare/commit boundary becomes explicit, typed, and easier to evolve safely.
- **Positive:** HTTP, Telegram, and tests can use attribute access instead of fragile string keys.
- **Negative:** Several tests and handlers need coordinated updates during the refactor.
- **Follow-up:** Future prepare-phase features should extend `PreparedExpense` instead of reintroducing ad hoc dict keys.

## References
- `src/application/services/expense_service.py`
- `src/presentation/http/handlers/expense_api_handler.py`
- `src/presentation/telegram/handlers/expense_handler.py`
