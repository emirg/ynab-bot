# Spec: Third-Party Shared Expense Inference

## Metadata
- **Status:** Implemented
- **Owner:** Codex
- **Related Roadmap Item:** E.31 Splitwise Responsibility Semantics follow-up
- **Harness Roadmap Marker:** ### E.32 — Third-Party Shared Expense Inference [COMPLETADO]
- **Related ADRs:** None

## Summary
Shared-expense parsing must treat messages where a configured split person paid or bought something as relevant shared-expense input. The bot receives expense-registration messages, so "Frank gasto 71800 en Pret" should not be interpreted as casual reporting about Frank; it should infer a 50/50 shared expense paid by Frank unless the message explicitly says the user is not involved. Likewise, "Frank me compro ..." must be a 100% user-responsibility third-party-paid shared expense.

## Problem
- Messages such as "Frank me compro un agua oxigenada..." can be misclassified as user-paid expenses categorized to Splitwise.
- Messages such as "Frank gasto 71800 en Pret" lack explicit "conmigo" wording but still represent shared expenses in the bot's operating context.
- The parser prompt and tests do not yet protect these natural Spanish patterns.

## Goals
- Infer `shared_expense`, `payer=other`, and `proportion=1` for "me compro" / "por mi" / "para mi" third-party-paid messages.
- Infer `shared_expense`, `payer=other`, and default 50/50 for configured-person paid/gastó messages without explicit proportion.
- Preserve the existing no-op behavior when the parsed result explicitly says the user has zero responsibility.

## Non-Goals
- Introduce a direct Splitwise API integration.
- Infer expenses for unknown people without the existing split alias flow.
- Change non-shared expense category matching outside these third-party-paid patterns.

## Users / Consumers
- Telegram users registering shared expenses in Spanish.
- HTTP text expense consumers that reuse the same `ExpenseService` parser pipeline.

## Expected Behavior
- "Frank me compro un agua oxigenada en Farmatodo por 14200" creates a `Shared Transactions` zero-sum transaction with Healthcare `-14200` and Gastos Splitwise `+14200`.
- "Frank gasto 71800 en Pret" creates a `Shared Transactions` zero-sum transaction for 50% of the amount in the real category and a matching positive Splitwise tracking leg.
- If the parser returns `payer=other` and `proportion=null` for a known split person, service normalization keeps default 50/50.

## Inputs and Outputs
- **Inputs:** Telegram or HTTP text messages, configured split aliases, configured shared account, YNAB categories/accounts/payees.
- **Outputs:** YNAB transaction payloads, Telegram success/error messages, HTTP serialized responses through the existing contract.
- **Public Interfaces:** No new public command, endpoint, or response field.

## Business Rules and Constraints
- User-facing messages remain Spanish.
- YNAB milliunit and source-of-truth invariants remain unchanged.
- `payer=other` means the transaction must use the configured shared account.
- The absence of "conmigo" after a configured person's "gasto/pago/compro" does not make the expense irrelevant.

## Edge Cases and Failure Handling
- If no alias exists for the extracted person, preserve the existing `/splitwise` alias error.
- If no shared account exists for `payer=other`, preserve the existing shared-account error.
- If future parser output explicitly indicates the user has no share, preserve the existing Spanish no-op message.

## Acceptance Criteria
- [x] The parser prompt includes explicit examples for "Frank me compro..." and "Frank gasto ... en Pret".
- [x] Parser tests protect the intended structured output for both patterns.
- [x] Service tests prove the two parsed forms produce `payer=other`, normalized shares, and shared account usage.
- [x] Domain payload tests prove the expected zero-sum category shapes.
- [x] Harness/docs verification passes.

## Open Questions
- None.

## References
- `docs/specs/archive/2026-05-03-splitwise-expense-semantics.md`
