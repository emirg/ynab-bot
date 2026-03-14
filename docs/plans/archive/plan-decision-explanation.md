# Plan: Explicacion de Decisiones (Milestone 1.3)

## Objective & Context
- **Status:** Completed
- **Goal:** When the bot records an expense, include a brief Spanish explanation of *why* it chose that category — whether from learned payee associations or LLM suggestion.
- **Why:** Users currently see the category and confidence percentage but have no insight into the decision logic. This transparency builds trust, helps users spot errors faster, and makes the learning system more tangible.

## Design Decisions

### Where the explanation originates

The `ExpenseService` is the only place that knows whether the final category came from learning (`_enhance_with_learning`) or from the LLM parser. The explanation must be assembled there, not in the formatter.

### How it flows to the formatter

 a new `category_explanation: Optional[str]` field on the `Expense` dataclass. This keeps it inside the existing data path: `ExpenseService` sets it, `ExpenseResult` carries the `Expense`, and `ExpenseResponseFormatter.format_success()` reads it. No new fields on `ExpenseResult` or `MessageResult` are needed.

### What the explanation says

Two variants (Spanish, one line each):

| Source | Template | Example |
|--------|----------|---------|
| Learning override | `"aprendido de tus ultimas {count} compras en {payee}"` | `"aprendido de tus ultimas 5 compras en McDonald's"` |
| LLM (high confidence >0.7) | `"sugerido por IA, confianza {pct}%"` | `"sugerido por IA, confianza 85%"` |
| LLM (low confidence <=0.7, no learning) | `"sugerido por IA, confianza {pct}% - considera verificar"` | `"sugerido por IA, confianza 42% - considera verificar"` |
| Receipt (parser_source='receipt') | `"detectado del recibo, confianza {pct}%"` | `"detectado del recibo, confianza 90%"` |

### Data needed for the explanation

- **Learning path:** `predict_category` must return the mapping `count` alongside `(category_id, confidence)`. Currently it returns `Tuple[str, float]`. We extend it to `Tuple[str, float, int]` where the third element is the payee-specific count for the winning category. This also requires updating `LearningRepository` interface and `SQLiteLearningRepository`.
- **LLM path:** `confidence` and `parser_source` already exist on `Expense`.

### Payee name format in explanation (RESOLVED)

Use the raw `expense.payee` (e.g., "McDonald's") rather than the normalized form (e.g., "mcdonalds"). Rationale: readability for the end user outweighs internal consistency with the learning system's normalized key. The user sees the name as they wrote it or as the LLM extracted it.

### Where the explanation is displayed

`ExpenseResponseFormatter.format_success()` — replace the current `*Procesado por:*` line with a `*Razon:*` line using `expense.category_explanation`. The confidence percentage and parser source are already embedded in the explanation text, so the separate `*Confianza:*` and `*Procesado por:*` lines are removed to avoid redundancy and keep the message brief.

## Prerequisites (Manual)
- [x] None. No env vars, no infra changes needed.

## Implementation Steps
*(Models MUST mark steps with [x] as they are completed and save the file)*

### [x] Step 1: Extend `predict_category` return type to include count
- **Files:** `src/domain/repositories/learning_repository.py`, `src/infrastructure/repositories/sqlite_learning_repository.py`
- **Action:**
  - Change `predict_category` return type from `Optional[Tuple[str, float]]` to `Optional[Tuple[str, float, int]]`.
  - In `SQLiteLearningRepository.predict_category()`, the `best` row already has `best['count']`. Return it as the third tuple element: `return best_category_id, confidence, best['count']`.
  - Update the abstract method signature and docstring in `LearningRepository`.
- **Tests:** `tests/test_sqlite_learning_repository.py` — Update existing `predict_category` tests to assert the third element (count) is returned. Add a test verifying the count value is correct for the winning category.

### [x] Step 2: Add `category_explanation` field to `Expense`
- **Files:** `src/domain/models/expense.py`
- **Action:**
  - Add `category_explanation: Optional[str] = None` field to the `Expense` dataclass (after `parser_source`, before `date`).
  - No changes to `to_ynab_format()` or `is_valid()` — the field is presentation-only.
- **Tests:** `tests/test_domain_models.py` — Add a test that a new `Expense` has `category_explanation=None` by default, and that it can be set.

### [x] Step 3: Build explanation in `ExpenseService._enhance_with_learning`
- **Files:** `src/application/services/expense_service.py`
- **Action:**
  - Update the `_enhance_with_learning` method to unpack the new third element from `predict_category`:
    ```
    predicted_category_id, learning_confidence, mapping_count = prediction
    ```
  - When learning overrides the category (i.e., `learning_confidence > expense.confidence`), set:
    ```
    expense.category_explanation = f"aprendido de tus ultimas {mapping_count} compras en {expense.payee}"
    ```
  - When learning does NOT override (high-confidence LLM), do not set explanation here — it will be set in the next step.
- **Tests:** `tests/test_expense_service.py` — Add/update tests for `_enhance_with_learning`:
  - When learning overrides: verify `expense.category_explanation` contains "aprendido" and the count.
  - When learning does not override: verify `category_explanation` is not set by this method.

### [x] Step 4: Build explanation for non-learning paths
- **Files:** `src/application/services/expense_service.py`
- **Action:**
  - In `_process_parsed_expense` (used by `process_message` text path) and `process_receipt_image`, AFTER `_enhance_with_learning` returns, if `expense.category_explanation` is still `None` (learning didn't set it), set it based on parser_source:
    - `parser_source == 'receipt'`: `f"detectado del recibo, confianza {int(expense.confidence * 100)}%"`
    - `parser_source == 'llm'` and `confidence > 0.7`: `f"sugerido por IA, confianza {int(expense.confidence * 100)}%"`
    - `parser_source == 'llm'` and `confidence <= 0.7`: `f"sugerido por IA, confianza {int(expense.confidence * 100)}% - considera verificar"`
  - Extract this into a private helper `_build_category_explanation(expense: Expense) -> str` to avoid duplication across the three pipelines (`_process_parsed_expense`, `process_receipt_image`, `process_expense_message`).
  - Apply the same logic in `process_expense_message` (voice path).
- **Tests:** `tests/test_expense_service.py` — Add tests:
  - LLM high confidence: explanation says "sugerido por IA, confianza 85%".
  - LLM low confidence: explanation says "considera verificar".
  - Receipt: explanation says "detectado del recibo".
  - Learning override: explanation says "aprendido" (already covered in Step 3).

### [x] Step 5: Update `ExpenseResponseFormatter.format_success()`
- **Files:** `src/presentation/telegram/formatters.py`
- **Action:**
  - Replace the two lines:
    ```
    {confidence_emoji} *Confianza:* {expense.confidence*100:.0f}%
    *Procesado por:* {expense.parser_source.upper()}
    ```
    with a single line:
    ```
    {confidence_emoji} *Razon:* {expense.category_explanation or 'desconocido'}
    ```
  - Keep the `confidence_emoji` logic (fire/check/warning) as it provides quick visual feedback.
- **Tests:** `tests/test_formatters.py` — Update `TestExpenseResponseFormatter`:
  - `test_format_success`: assert "Razon" is present and "aprendido" or "sugerido" appears.
  - `test_format_success_no_explanation`: when `category_explanation` is `None`, assert "desconocido" appears.
  - Remove or update assertions that check for "LLM" or "Confianza" since those lines are removed.

### [x] Step 6: Update `conftest.py` fixtures
- **Files:** `tests/conftest.py`
- **Action:**
  - Update `mock_learning_repository` fixture: `predict_category.return_value = None` stays the same (it's a 3-tuple or None, and None is fine).
  - Update `sample_expense` fixture to include `category_explanation='sugerido por IA, confianza 85%'` so formatter tests work with the new field.
- **Tests:** Run full test suite to verify no regressions.

### [x] Step 7: Final integration check
- **Files:** (none — verification only)
- **Action:** Run `pytest` to ensure all ~349+ tests pass. Verify coverage stays at ~86%+.
- **Tests:** Full suite.

## Constraints & Architecture
- The explanation is **presentation-only** — it does not affect YNAB transaction creation, learning storage, or any business logic.
- `category_explanation` is a plain string to keep formatting decisions in one place (`ExpenseService`) rather than spreading data (count, source, confidence) across layers for the formatter to assemble.
- All explanation strings are in **Spanish** per project convention.
- The `predict_category` return type change is backward-compatible: callers that destructure `(cat_id, conf)` will need updating, but there is only one caller (`_enhance_with_learning`).
- No database migration needed — `category_explanation` is a runtime-only field.

## Risks & Open Questions
1. **`predict_category` callers:** Verify there are no other callers of `predict_category` besides `_enhance_with_learning`. (Confirmed: only one caller in the codebase.)
2. **Message length:** The added explanation line is short (~50 chars max). No risk of hitting Telegram's 4096-char message limit.
3. **Payee name in explanation:** RESOLVED -- Use raw `expense.payee` (e.g., "McDonald's") for readability. Confirmed by user. See "Payee name format in explanation" in Design Decisions.

## Verification
- [x] Send a text expense for a payee with existing learning data — response shows "aprendido de tus ultimas N compras en X"
- [x] Send a text expense for a new payee — response shows "sugerido por IA, confianza X%"
- [x] Send a photo receipt — response shows "detectado del recibo, confianza X%"
- [x] Send a voice message expense — response shows appropriate explanation
- [x] Send a low-confidence expense — response shows "considera verificar"
- [x] `pytest` passes with ~86%+ coverage
