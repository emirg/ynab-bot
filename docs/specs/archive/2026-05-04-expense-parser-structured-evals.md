# Spec: Expense Parser Structured Outputs and Golden Evals

## Metadata
- **Status:** Implemented
- **Owner:** Codex
- **Related Roadmap Item:** Parser reliability hardening
- **Related ADRs:** None
- **Harness Roadmap Marker:** ### E.33 — Expense Parser Structured Outputs and Golden Evals [COMPLETADO]

## Summary
The expense parser should move from free-form JSON responses toward a schema-constrained contract, while gaining a golden scenario battery for validating parser behavior across models. The first delivery uses a hybrid evaluation approach: CI validates fixtures, schemas, and deterministic parser behavior without network access; a manual command performs real OpenAI model comparisons when explicitly run by a developer.

## Problem
- `LLMExpenseParser` currently asks the model to return JSON but validates the shape only after receiving free-form text.
- Parser regressions around Splitwise semantics show that prompt wording alone is not enough; the contract needs stricter shape guarantees and repeatable scenario coverage.
- Model upgrades cannot be evaluated safely because there is no versioned golden battery that compares candidate models against expected parser outputs.

## Goals
- Define strict parsed-output schemas for expense, query, and shared-expense intents.
- Move parser calls to OpenAI Structured Outputs where supported.
- Make the expense parser model configurable without code edits.
- Add a versioned golden scenario battery covering common and high-risk messages.
- Add deterministic CI coverage for fixture validity and schema compatibility without calling OpenAI.
- Add a manual real-model evaluation command that compares `gpt-4o-mini`, `gpt-5.4-nano`, `gpt-5.4-mini`, or any explicitly supplied model against the same scenario set.

## Non-Goals
- Do not change the default parser model in the first implementation.
- Do not make live OpenAI calls part of normal CI.
- Do not rewrite `ExpenseService` transaction construction.
- Do not remove legacy `split_amount` compatibility.
- Do not add fine-tuning, distillation, or provider abstraction.

## Users / Consumers
- Bot users who depend on accurate expense and Splitwise registration.
- Developers evaluating parser prompt/model changes.
- Future AI agents that need executable parser contracts before touching model behavior.

## Expected Behavior
- `LLMExpenseParser.parse_message()` continues returning dictionaries compatible with the current service layer.
- The parser asks OpenAI for a schema-constrained response instead of plain free-form JSON where the active SDK/model supports it.
- The parser model is read from configuration or environment, with `gpt-4o-mini` preserved as the initial default.
- Golden fixtures live in the repository and declare message input, available categories/accounts when relevant, and expected parsed fields.
- CI validates that every golden fixture is internally coherent and can be represented by the parser schema without network access.
- A manual evaluator can call real OpenAI models and report pass/fail results per scenario and per field.

## Inputs and Outputs
- **Inputs:** Natural-language expense messages, YNAB category/account lists, optional learning hints, timezone, parser model configuration, golden fixture files.
- **Outputs:** Parsed expense/query/shared-expense dictionaries, fixture validation results, manual evaluation reports.
- **Public Interfaces:** `LLMExpenseParser.parse_message()`, `LLMExpenseParser.parse_expense()`, `LLMExpenseParser.parse_receipt_image()`, environment/config model setting, manual eval CLI.

## Business Rules and Constraints
- Telegram-facing runtime errors remain in Spanish.
- Developer-facing docs, fixture metadata, and eval output default to English.
- YNAB category/account names must remain exact names from provided lists.
- Splitwise semantics remain deterministic after parsing: `payer`, user share, other share, and account routing are not guessed downstream.
- CI must remain deterministic and must not require `OPENAI_API_KEY`.
- Manual eval commands may require `OPENAI_API_KEY` and must make that requirement explicit.
- Real-model eval failures should be diagnostic, not automatically rewritten into looser expected fixtures.

## Edge Cases and Failure Handling
- If a model returns a schema-invalid response, parser behavior should remain a clean parse failure rather than partial unsafe data.
- If the configured parser model is missing, the application falls back to the documented default.
- If manual eval runs without `OPENAI_API_KEY`, it exits with a clear error.
- If a fixture expects conflicting fields, deterministic fixture validation fails before any network call.
- If a candidate model returns a valid schema but wrong semantics, the evaluator reports field-level mismatches.

## Acceptance Criteria
- [x] Parser output schemas cover `expense`, `query`, and `shared_expense` without breaking existing service consumers.
- [x] Parser calls use Structured Outputs for message parsing where supported.
- [x] The parser model can be configured externally and defaults to the current model for compatibility.
- [x] A golden fixture suite covers at least normal expenses, queries, dates, category/account ambiguity, and Splitwise responsibility cases.
- [x] CI validates golden fixtures and schemas without OpenAI network calls.
- [x] A manual eval command can compare multiple real OpenAI models and produce field-level results.
- [x] Existing parser/service/domain tests continue passing.

## Open Questions
- Receipt image parsing is deferred to a later slice; this delivery is text-only for `parse_message()`.
- The exact pass threshold for changing the default model remains a future explicit decision.

## Harness Roadmap Marker
### E.33 — Expense Parser Structured Outputs and Golden Evals [COMPLETADO]

## References
- `src/parsers/llm_expense_parser.py`
- `tests/parsers/test_llm_expense_parser.py`
- `docs/specs/archive/2026-05-03-splitwise-expense-semantics.md`
- `docs/specs/archive/2026-05-04-third-party-shared-expense-inference.md`
