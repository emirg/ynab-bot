# Plan: Expense Parser Prompt Refinement

## Objective & Context
- **Status:** Completed
- **Source Spec:** `docs/specs/2026-05-04-expense-parser-prompt-refinement.md`
- **Harness Roadmap:** Ignore
- **Goal:** Update the prompt generation logic in `src/parsers/llm_expense_parser.py` to restore missing context and add safeguards.
- **Approach:** Modify `_generate_message_system_prompt` to inject the missing string blocks, add few-shot examples, and refine the `REGLAS CRÍTICAS`.

## Affected Components
- `src/parsers/llm_expense_parser.py` — Update system prompt string blocks.

## Prerequisites (Manual)
- [x] None

## Implementation Steps

### Group 1

#### [x] Step 1: Update Account Detection block
- **Files:** `src/parsers/llm_expense_parser.py`
- **Action:** In `_generate_message_system_prompt`, modify the `accounts_text` construction to include instructions for detecting accounts in expenses ("con mi [cuenta]") as well as the existing query instructions.
- **Tests:** `tests/parsers/`

#### [x] Step 2: Update Learning Hints block
- **Files:** `src/parsers/llm_expense_parser.py`
- **Action:** In `_generate_message_system_prompt`, update `learning_hints_section` to explicitly instruct the model to choose the highest percentage if no explicit clues exist.
- **Tests:** `tests/parsers/`

#### [x] Step 3: Add Currency, Few-Shot Examples, and Collision Rule to Main Prompt
- **Files:** `src/parsers/llm_expense_parser.py`
- **Action:** In the main f-string returned by `_generate_message_system_prompt`:
  1. Add `FORMATO DE MONEDA COLOMBIANA` block before the `CONSULTAS` section.
  2. Add a `EJEMPLOS DE GASTOS REGULARES Y CONSULTAS` block with one expense and one query example right before the `EJEMPLOS DE GASTOS COMPARTIDOS`.
  3. Add rules for Cuentas vs Categorias, Moneda, Colisión de nombres, and Historial to the `REGLAS CRÍTICAS` block.
- **Tests:** `tests/parsers/`

## Constraints & Architecture
- Maintain the strict JSON schema required by `gpt-4o-mini` and `gpt-5-mini`.
- Do not alter python class signatures.

## Verification
- [x] Run `python src/parsers/llm_expense_parser.py` and verify all tests pass.
- [x] Check behavioral invariant harness: `.venv/bin/python scripts/harness/verify.py --ci`
