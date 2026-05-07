# ADR: Use gpt-5-mini as Default Expense Parser

## Metadata
- **Status:** Accepted
- **Date:** 2026-05-04
- **Related Spec:** `docs/specs/archive/2026-05-04-update-parser-model-gpt-5-mini.md`
- **Related Plan:** `docs/plans/archive/2026-05-04-update-parser-model-gpt-5-mini.md`
- **Supersedes:** None
- **Superseded By:** None

## Context
A multi-model evaluation was performed on 2026-05-04 comparing `gpt-4o-mini`, `gpt-5-nano`, and `gpt-5-mini` against a consolidated "golden" dataset of 31 scenarios.

Results:
- `gpt-5-mini`: 77% accuracy (24/31). Handled Splitwise logic ("por Frank", "con Frank") with high precision.
- `gpt-4o-mini`: 71% accuracy (22/31). Occasionally missed intents or failed on payee normalization.
- `gpt-5-nano`: 38% accuracy (12/31). High failure rate due to output length limits and empty responses.

## Decision
We will set `gpt-5-mini` as the default model for the textual expense parser.

## Consequences
- **Positive**: Higher accuracy for complex user inputs, especially shared expenses.
- **Negative**: Potentially higher latency/cost compared to `gpt-4o-mini` (though still in the "mini" tier).
- **Technical**: Requires using `max_completion_tokens` instead of `max_tokens`, which is already handled by our compatibility layer.
