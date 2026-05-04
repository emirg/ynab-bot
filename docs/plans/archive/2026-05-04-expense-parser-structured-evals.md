# Plan: Expense Parser Structured Outputs and Golden Evals

## Objective & Context
- **Status:** Completed
- **Source Spec:** `docs/specs/2026-05-04-expense-parser-structured-evals.md`
- **Goal:** Add schema-constrained parser outputs and a hybrid golden evaluation suite for safe model comparison.
- **Approach:** Introduce typed parser response schemas first, validate fixtures without network in CI, then add manual real-model evaluation while preserving the current parser model default.
- **Harness Roadmap Marker:** ### E.33 — Expense Parser Structured Outputs and Golden Evals [COMPLETADO]

## Affected Components
- `src/parsers/llm_expense_parser.py` — use configurable model and schema-constrained responses.
- `src/parsers/expense_parser_schemas.py` — new typed parser response schema module.
- `src/infrastructure/config/app_config.py` — expose parser model configuration if the existing config surface is the right place after inspection.
- `tests/parsers/test_llm_expense_parser.py` — preserve existing behavior and assert structured-output request shape.
- `tests/parsers/test_expense_parser_schemas.py` — validate schema behavior and edge cases.
- `tests/evals/test_expense_parser_golden_fixtures.py` — deterministic fixture validation without OpenAI calls.
- `tests/fixtures/expense_parser_golden/*.yaml` or `.json` — golden scenario battery.
- `scripts/evals/evaluate_expense_parser.py` — manual real-model evaluator.
- `docs/dev/README.md` — document manual eval usage and required env vars.
- `docs/ARCHITECTURE.md` — update parser architecture notes.

## Prerequisites (Manual)
- [x] User confirms whether receipt-image scenarios are included in the first delivery or deferred.
- [x] User confirms model-change threshold policy before any future default-model change.
- [x] Manual real-model eval requires `OPENAI_API_KEY`; CI fixture validation must not.

## Implementation Steps
*(Models MUST mark steps with [x] as they are completed and save the file)*

### Group 1
<!-- Establish the typed parser contract without changing runtime calls. -->

#### [x] Step 1: Add parser schema tests
- **Files:** `tests/parsers/test_expense_parser_schemas.py`
- **Action:** Add failing tests for valid `expense`, `query`, and `shared_expense` payloads; invalid intent; invalid payer; invalid confidence; invalid or conflicting share amounts.
- **Tests:** `rtk .venv/bin/pytest tests/parsers/test_expense_parser_schemas.py -q`

#### [x] Step 2: Implement parser schemas
- **Files:** `src/parsers/expense_parser_schemas.py`
- **Action:** Add typed models that represent the current parser dictionary contract and expose a normalisation method returning dicts compatible with `ExpenseService`.
- **Tests:** `rtk .venv/bin/pytest tests/parsers/test_expense_parser_schemas.py -q`

### Group 2 (depends on: Group 1)
<!-- Add deterministic golden fixtures and validate them locally. -->

#### [x] Step 3: Add first golden fixture batch
- **Files:** `tests/fixtures/expense_parser_golden/initial.json`
- **Action:** Add 30-50 scenarios covering basic expenses, queries, relative dates, explicit accounts, ambiguous payees/categories, and Splitwise responsibility cases including recent regressions.
- **Tests:** Fixture validation test added in Step 4.

#### [x] Step 4: Add fixture validation tests
- **Files:** `tests/evals/test_expense_parser_golden_fixtures.py`
- **Action:** Validate fixture file shape, unique IDs, expected fields, and schema compatibility without calling OpenAI.
- **Tests:** `rtk .venv/bin/pytest tests/evals/test_expense_parser_golden_fixtures.py -q`

### Group 3 (depends on: Group 1)
<!-- Wire schemas into parser runtime while preserving external behavior. -->

#### [x] Step 5: Add configurable parser model
- **Files:** `src/parsers/llm_expense_parser.py`, `tests/parsers/test_llm_expense_parser.py`
- **Action:** Replace hardcoded message parser model with an env/config-backed value that defaults to `gpt-4o-mini`.
- **Tests:** Add tests for default model and environment override.

#### [x] Step 6: Use Structured Outputs for message parsing
- **Files:** `src/parsers/llm_expense_parser.py`, `tests/parsers/test_llm_expense_parser.py`
- **Action:** Request a schema-constrained response for `parse_message()` and normalise the validated response back to the existing dictionary contract.
- **Tests:** Existing parser tests plus new tests asserting structured-output request shape and parse failure behavior.

#### [x] Step 7: Decide legacy parser and receipt path scope
- **Files:** `src/parsers/llm_expense_parser.py`, `tests/parsers/test_llm_expense_parser.py`
- **Action:** Based on the prerequisite decision, either keep `parse_expense()` and `parse_receipt_image()` on the current free-form path with documented follow-up, or apply the same schema pattern where safely supported.
- **Tests:** Existing legacy and receipt parser tests remain green.

### Group 4 (depends on: Groups 2 and 3)
<!-- Add manual real-model evaluation. -->

#### [x] Step 8: Add manual evaluator CLI
- **Files:** `scripts/evals/evaluate_expense_parser.py`
- **Action:** Load golden fixtures, instantiate parser with supplied model(s), call real OpenAI only when explicitly run, and report scenario/field mismatches.
- **Tests:** Add unit coverage with parser/OpenAI mocked so CI does not require network.

#### [x] Step 9: Document eval workflow
- **Files:** `docs/dev/README.md`, `docs/ARCHITECTURE.md`
- **Action:** Document fixture validation, manual model comparison, required `OPENAI_API_KEY`, and the rule that model default changes require evidence from the golden suite.
- **Tests:** `rtk .venv/bin/python scripts/harness/check_docs.py`

## Constraints & Architecture
- Keep `ExpenseService` consumers compatible with current parser dictionaries.
- Preserve `gpt-4o-mini` as the initial default until a later explicit model-change decision.
- Keep CI deterministic and network-free.
- Use structured parsing and deterministic validation; do not loosen domain rules to match a candidate model.
- Maintain Spanish Telegram UX and English developer docs.
- Follow milliunit and Splitwise responsibility invariants already enforced in domain/service tests.

## Verification
- [x] `rtk .venv/bin/pytest tests/parsers/test_expense_parser_schemas.py -q`
- [x] `rtk .venv/bin/pytest tests/evals/test_expense_parser_golden_fixtures.py -q`
- [x] `rtk .venv/bin/pytest tests/parsers/test_llm_expense_parser.py -q`
- [x] `rtk .venv/bin/python scripts/harness/check_docs.py`
- [x] `rtk .venv/bin/python scripts/harness/verify.py --ci`
- [x] `rtk .venv/bin/pytest`
- [x] Manual, optional: `rtk .venv/bin/python scripts/evals/evaluate_expense_parser.py --model gpt-4o-mini --model gpt-5.4-nano --model gpt-5.4-mini`

## Harness Roadmap Marker
### E.33 — Expense Parser Structured Outputs and Golden Evals [COMPLETADO]
