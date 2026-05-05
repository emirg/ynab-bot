# Spec: Expense Parser Prompt Refinement

## Metadata
- **Status:** Implemented
- **Owner:** AI Assistant (Orchestrator)
- **Related Roadmap Item:** Technical Debt / Parsing Accuracy

## Summary
The system prompt used in `LLMExpenseParser._generate_message_system_prompt` suffered from regressions when it was rewritten to support Structured Outputs and intent routing (Query vs Expense vs Shared Expense). This spec outlines the restoration of missing context rules (currency format, explicit account detection for expenses, few-shot examples for non-shared intents) and the addition of conflict resolution rules (person vs. category name collision, explicit history tie-breaking) to improve the reliability and accuracy of expense parsing.

## Problem
- The prompt lost the explicit `FORMATO DE MONEDA COLOMBIANA` block, forcing the model to infer informal Colombian currency formats ("k", "lucas").
- The account detection instructions for expenses were replaced with instructions meant solely for queries. The model is no longer explicitly instructed on how to extract an account when a user reports an expense (e.g., "con mi Nequi").
- There are no few-shot examples for normal expenses or queries, while there are 13 examples for shared expenses, potentially biasing the model toward classifying ambiguous inputs as shared expenses.
- Lack of explicit collision handling: a shared expense person named "Eli" can collide with the category "🤝Eli a.k.a Gastos E²", causing the model to misassign the category.
- The `learning_hints` block lacks a tie-breaker rule for when the message provides no additional context to pick between historical categories (e.g., 67% vs 33%).

## Goals
- Restore the Colombian currency parsing rules to the message parser prompt.
- Restore account detection instructions specifically for expense intents.
- Provide baseline few-shot examples for standard expenses and queries.
- Add explicit collision resolution for person names vs category names.
- Clarify tie-breaking rules for historical learning hints.

## Non-Goals
- Modifying the underlying parser schema or return types.
- Modifying the receipt parser prompt (`_generate_receipt_system_prompt`).
- Changing the retry mechanism or API parameters.

## Users / Consumers
- End-users reporting expenses through the bot.

## Expected Behavior
- When users say "gaste 20 lucas", it reliably parses as `20000.0`.
- When users say "en Carulla con Nu Card", it reliably maps `Nu Card` to the `account` field, rather than just knowing how to answer "cuanto tengo en Nu Card".
- Given a tie or lack of explicit context for a previously categorized payee, the model strictly obeys the highest historical percentage.
- "Eli" used as a payer/sharer does not accidentally trigger the category `🤝Eli a.k.a Gastos E²` unless explicitly justified by the payee context.

## Inputs and Outputs
- **Inputs:** User text messages.
- **Outputs:** JSON responses adhering to the existing `message_response_format_schema`.

## Business Rules and Constraints
- The schema for structured outputs must not be altered; all prompt changes must fit within the existing JSON expectations.

## Edge Cases and Failure Handling
- If the text is severely ambiguous, the model should continue returning a low `confidence` score or dropping to `intent: query` depending on context.

## Acceptance Criteria
- [ ] `FORMATO DE MONEDA COLOMBIANA` is present in the prompt.
- [ ] Account detection rules for expenses are present alongside query account rules.
- [ ] At least one example for a standard expense and one for a query are provided before shared expense examples.
- [ ] Collision rule is added to `REGLAS CRÍTICAS`.
- [ ] The `learning_hints` template dictates choosing the highest percentage if no explicit clues exist.
