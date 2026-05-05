# Spec: Update Parser Model to gpt-5-mini

## Metadata
- **Status:** Approved
- **Owner:** Gemini CLI
- **Related Roadmap Item:** "Modernize Parser Models"
- **Related ADRs:** docs/adrs/2026-05-04-gpt-5-mini-default-parser.md

## Summary
Update the default LLM model used for expense parsing from `gpt-4o-mini` to `gpt-5-mini`. This change is driven by evaluation results showing superior accuracy in complex shared expense scenarios and better overall consistency.

## Problem
- `gpt-4o-mini` has shown inconsistencies in detecting `shared_expense` intents and sometimes confuses "Meal delivery" with "Dining out".
- `gpt-4o-mini` failed to correctly normalize certain payees (e.g., "Transmilenio") compared to newer models.

## Goals
- Improve parsing accuracy for complex Spanish natural language inputs.
- Ensure the system is fully compatible with `gpt-5` series parameters (e.g., `max_completion_tokens` vs `max_tokens`).

## Non-Goals
- Updating Vision models (remaining on `gpt-4o-mini` for now per roadmap).
- Changing the prompt engineering logic.

## Users / Consumers
- End users interacting with the Telegram bot.

## Expected Behavior
- The system defaults to `gpt-5-mini` for all textual expense parsing.
- Model-specific parameter handling (temperature stripping, completion token naming) happens automatically.

## Business Rules and Constraints
- Must respect the `OPENAI_EXPENSE_PARSER_MODEL` environment variable override.
- Must follow the OpenAI model compatibility layer recently implemented.

## Acceptance Criteria
- [ ] Default model is `gpt-5-mini`.
- [ ] CI tests pass with the new default.
- [ ] Manual evaluation shows higher accuracy on the golden suite.
