# Spec: Splitwise Expense Semantics

## Metadata
- **Status:** Implemented
- **Owner:** Codex
- **Related Roadmap Item:** Milestone 2.2 / 2.3 shared expenses
- **Harness Roadmap Marker:** ### E.31 — Splitwise Responsibility Semantics [COMPLETADO]
- **Related ADRs:** None

## Summary
Shared expense parsing must distinguish who paid from who is financially responsible for the purchase. Messages such as "gaste en Carulla con Eli", "gaste por Eli", "Eli gasto conmigo", and "Eli gasto por mi" currently rely on ambiguous LLM fields that can invert the YNAB result. This feature defines a deterministic contract for converting natural-language shared-expense messages into YNAB transactions and Splitwise tracking entries.

## Problem
- The current shared-expense parser depends on a small set of fields (`payer`, `proportion`, `split_amount`) whose meaning is easy for the LLM to invert.
- The system does not have a complete behavior matrix that protects real user phrases against wrong YNAB transaction construction.
- 100% responsibility cases should not create split transactions with zero-value category legs.

## Goals
- Define deterministic rules for shared expenses based on payer and responsibility.
- Preserve the YNAB source-of-truth and milliunit invariants.
- Ensure common Spanish phrases map to stable YNAB transaction shapes.
- Avoid zero-amount split lines when one party is responsible for 100% of the expense.
- Add acceptance criteria that can be translated into parser, service, domain, and behavioral-invariant tests.

## Non-Goals
- Changing Splitwise configuration, alias management, or the `/splitwise` command.
- Introducing a direct Splitwise API integration.
- Changing regular non-shared expense behavior.
- Changing category selection rules beyond the shared-expense transaction shape.

## Users / Consumers
- Telegram users registering shared expenses in Spanish.
- HTTP expense endpoint consumers that use the same `ExpenseService` shared-expense flow.
- Maintainers and AI agents working on parser, domain model, and YNAB transaction construction.

## Expected Behavior
The system must first determine:

- **Payer:** who paid the merchant or vendor.
- **User share:** the amount the bot user is financially responsible for.
- **Other share:** the amount the other person is financially responsible for.

Then it must create the YNAB transaction based on the payer and shares.

### Language Rules
- `yo gaste/pague/compre ... con <persona>` means the user paid and the default split is 50/50.
- `yo gaste/pague/compre ... por <persona>` or `para <persona>` means the user paid for the other person and the default user share is 0%.
- `<persona> gasto/pago/compro ... conmigo` means the other person paid and the default split is 50/50.
- `<persona> gasto/pago/compro ... por mi` or `para mi` means the other person paid for the user and the default user share is 100%.
- Explicit proportions override defaults.
- Explicit fixed amounts must be interpreted by textual owner:
  - `70k son de Eli`, `70k son para Eli`, or `70k son por Eli` means Eli's share is 70k.
  - `70k son mios`, `mi parte son 70k`, or equivalent wording means the user's share is 70k.
  - If the message says the other person's share, user share is `total - other_share`.
  - If the message says the user's share, other share is `total - user_share`.

### YNAB Transaction Rules
- If the user paid and both shares are greater than zero:
  - Use the user's real payment account, normally the configured/default account or the account inferred from the message.
  - Create a split transaction whose real category leg is `-user_share`.
  - Create a Splitwise tracking category leg of `-other_share`.
- If the user paid and user share is zero:
  - Create a regular transaction in the user's payment account.
  - Categorize the full amount as the Splitwise tracking category.
  - Do not create a split transaction with a zero real-category leg.
- If the user paid and other share is zero:
  - Create a regular transaction in the user's payment account.
  - Categorize the full amount as the real expense category.
  - Do not create a split transaction with a zero Splitwise leg.
- If the other person paid and user share is greater than zero:
  - Use the configured `Shared Transactions` account.
  - Create a zero-sum transaction.
  - Add a real-category outflow of `-user_share`.
  - Add a Splitwise tracking category inflow of `+user_share`.
- If the other person paid and user share is zero:
  - Do not create a YNAB transaction.
  - Return a Spanish message explaining that there is no user expense or debt to register.

## Inputs and Outputs
- **Inputs:** Telegram text messages, HTTP text expense payloads, configured Splitwise category aliases, configured shared account, YNAB category/account/payee lists.
- **Outputs:** YNAB transactions, Spanish preview/success/error messages, HTTP response payloads for preview/commit flows.
- **Public Interfaces:** Telegram expense message flow, HTTP expense endpoint, shared `ExpenseService` parse/prepare/commit flow.

## Business Rules and Constraints
- YNAB amounts are milliunits in API payloads; expenses are negative.
- YNAB remains the financial source of truth.
- User-visible Telegram text must remain Spanish.
- Per-user Splitwise aliases and shared account configuration must remain isolated.
- The parser may use an LLM, but transaction construction must be deterministic once payer and shares are known.
- A 100% responsibility case must not be represented as a split transaction with a zero-value category leg.

## Behavior Matrix
| Message | Account | Expected YNAB Category Shape |
|---|---|---|
| `Gaste 200k en Carulla con Eli` | User payment account, e.g. `RappiCard` | Split: `Groceries -100k`, `Gastos Splitwise -100k` |
| `Eli gasto 200k en Carulla conmigo` | `Shared Transactions` | Zero-sum split: `Groceries -100k`, `Gastos Splitwise +100k` |
| `Gaste 100k en Carulla por Eli` | User payment account, e.g. `RappiCard` | Regular transaction: `Gastos Splitwise -100k` |
| `Eli gasto 200k por mi en Carulla` | `Shared Transactions` | Zero-sum split: `Groceries -200k`, `Gastos Splitwise +200k` |
| `Gaste 200k en Carulla con Eli, 70k son de Eli` | User payment account | Split: `Groceries -130k`, `Gastos Splitwise -70k` |
| `Eli gasto 200k en Carulla conmigo, 70k son mios` | `Shared Transactions` | Zero-sum split: `Groceries -70k`, `Gastos Splitwise +70k` |
| `Eli gasto 200k en Carulla conmigo, 70k son de Eli` | `Shared Transactions` | Zero-sum split: `Groceries -130k`, `Gastos Splitwise +130k` |
| `Gaste 200k en Carulla con Eli, todo es mio` | User payment account | Regular transaction: `Groceries -200k` |

## Edge Cases and Failure Handling
- If a fixed share amount is greater than the total, reject the parsed shared expense with a Spanish error instead of creating an invalid transaction.
- If both user share and other share are missing, default to 50/50 only when the message implies a shared expense (`con <persona>` or `conmigo`).
- If the message names a person without a configured Splitwise alias, keep the current `/splitwise` error behavior.
- If `payer=other` and no shared account is configured, keep the current Spanish `/splitwise` error behavior.
- If the parser returns conflicting fixed-share fields, reject the shared expense with a clear Spanish error explaining that the declared parts do not match the total.
- If a zero-share branch produces a regular transaction, previews and success messages must describe the one-category result clearly.

## Acceptance Criteria
- [x] The four provided scenarios produce the exact account and category-shape behavior in the matrix.
- [x] User-paid 100% other-responsibility cases create a regular Splitwise-category transaction, not a split transaction with a zero real-category leg.
- [x] User-paid 100% user-responsibility cases create a regular real-category transaction, not a split transaction with a zero Splitwise leg.
- [x] Other-paid user-share cases always use `Shared Transactions` and remain zero-sum.
- [x] Other-paid zero-user-share cases do not create YNAB transactions and return a Spanish no-op message.
- [x] Explicit fixed amounts can identify either the user's share or the other person's share.
- [x] Conflicting explicit share amounts are rejected with a Spanish message that explains why the expense was not accepted.
- [ ] The HTTP serializer keeps its existing external contract in the first implementation; normalized share fields may be used internally but are not required in the public response.
- [ ] Tests cover parser normalization, service share calculation, domain YNAB payloads, formatter output, and the behavior matrix.
- [ ] Documentation is updated so future agents treat payer and responsibility as separate concepts.

## Open Questions
- None.

## References
- `docs/AI_WORKFLOW.md`
- `docs/DOCUMENTATION_WORKFLOW.md`
- `docs/ARCHITECTURE.md`
- `docs/plans/archive/2.2_split_transactions.md`
- `docs/plans/archive/2.3_third_party_paid.md`
- `docs/plans/archive/2026-03-22-fix-inverted-splitwise-expenses.md`
