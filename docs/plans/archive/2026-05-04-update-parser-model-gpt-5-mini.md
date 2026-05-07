# Plan: Update Parser Model to gpt-5-mini

> **For Gemini CLI:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

## Objective & Context
- **Status:** Completed
- **Source Spec:** `docs/specs/2026-05-04-update-parser-model-gpt-5-mini.md`
- **Harness Roadmap:** Ignore
- **Goal:** Update the default expense parser model to `gpt-5-mini`.
- **Approach:** Modify the `LLMExpenseParser` default model constant and update environment variable references.

## Affected Components
- `src/parsers/llm_expense_parser.py` — Update default constant.
- `config/.env.example` — Update documentation.
- `config/.env.dev.example` — Update documentation.

## Prerequisites (Manual)
- [x] Ensure OpenAI API key has access to `gpt-5-mini`.

## Implementation Steps

### Group 1
<!-- Update constants and documentation -->

#### [x] Step 1: Update default model in code
- **Files:** `src/parsers/llm_expense_parser.py`
- **Action:** Change the default value for the model environment variable lookup.
- **Tests:** `tests/parsers/test_llm_expense_parser.py` — Verify that the parser instantiates with the new default when no env var is set.

#### [x] Step 2: Update example environment files
- **Files:** `config/.env.example`, `config/.env.dev.example`
- **Action:** Update the commented or example value for `OPENAI_EXPENSE_PARSER_MODEL`.

### Group 2 (depends on: Group 1)
<!-- Final Verification -->

#### [x] Step 3: Run regression tests
- **Files:** N/A
- **Action:** Run `.venv/bin/pytest tests/parsers/test_llm_expense_parser.py tests/parsers/test_openai_model_compatibility.py`
- **Expected:** All tests pass with the new default.

## Constraints & Architecture
- Follow the OpenAI model compatibility layer (temperature stripping).
- Do not hardcode the model where `gpt-4o-mini` is explicitly required (e.g., Vision).

## Verification
- [x] Run `LLMExpenseParser().expense_parser_model` in a shell and verify it is `gpt-5-mini`.
