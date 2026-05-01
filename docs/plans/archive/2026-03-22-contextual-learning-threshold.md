# Plan: Contextual Learning Threshold (Fix Inmediato)

## Objective & Context
- **Status:** Complete
- **Harness Roadmap:** Ignore
- **Goal:** Stop `_enhance_with_learning` from overriding the LLM's category when the payee has ambiguous history (multiple categories). Only override when learning confidence >= 0.95 (single-category payee).
- **Why:** A payee like "Movistar" can map to both "Internet" and "Teléfono". The current code unconditionally overwrites the LLM's decision (line 857), even when the LLM correctly interprets contextual hints in the message (e.g., "Movistar (internet)"). This causes incorrect categorization for multi-category payees.

## Affected Components
- `src/application/services/expense_service.py` — `_enhance_with_learning` method (lines 847-868)
- `tests/test_expense_service.py` — `TestEnhanceWithLearning` class (lines 334-402)

## Prerequisites (Manual)
- None

## Implementation Steps

### Group 1
<!-- Fix the threshold logic and update/add tests -->

#### [x] Step 1: Add confidence threshold to `_enhance_with_learning`
- **Files:** `src/application/services/expense_service.py`
- **Action:** In `_enhance_with_learning`, change the override condition on line 857 from unconditional (`if predicted_category_id != expense.category_id`) to gated by confidence:
  ```python
  if prediction:
      predicted_category_id, learning_confidence, mapping_count = prediction

      if predicted_category_id != expense.category_id:
          if learning_confidence >= 0.95:
              # High confidence: single-category payee — learning overrides LLM
              logger.info(f"Learning override for {expense.payee}: {predicted_category_id} "
                          f"(confidence: {learning_confidence:.2f}, count: {mapping_count})")
              expense.category_id = predicted_category_id
              expense.confidence = learning_confidence
              expense.category_explanation = f"aprendido de tus ultimas {mapping_count} compras en {expense.payee}"
              category = next((cat for cat in categories if cat.id == predicted_category_id), None)
              if category:
                  expense.category_name = category.name
          else:
              # Low confidence: multi-category payee — trust LLM, just log
              logger.info(f"Learning defers to LLM for {expense.payee}: learning={predicted_category_id} "
                          f"(confidence: {learning_confidence:.2f}), LLM={expense.category_id}")
  ```
  Key semantics: `confidence` from `predict_category` is `best_count / total_count`. A value of 1.0 means all past uses mapped to one category. Below 0.95 means the payee has been used with multiple categories.
- **Tests:** `tests/test_expense_service.py` — Update existing tests and add new ones (see Step 2)

#### [x] Step 2: Update and add tests for the new threshold behavior
- **Files:** `tests/test_expense_service.py`
- **Action:** Modify the `TestEnhanceWithLearning` class:
  1. **Update `test_high_confidence_overridden_if_learning_higher`** — This already uses confidence 1.0, so it should still pass (1.0 >= 0.95). No change needed, but verify.
  2. **Update `test_low_confidence_enhanced`** — Currently uses confidence 0.8 and expects override. With the new threshold, 0.8 < 0.95, so learning should NOT override. Update assertion: `result.category_id == 'cat-1'` (LLM's original), no explanation change.
  3. **Update `test_learning_always_wins_when_category_differs`** — Currently uses confidence 0.2 and expects override. With the new threshold, 0.2 < 0.95, so learning should NOT override. Update assertion: `result.category_id == 'cat-1'`.
  4. **Keep `test_equal_confidence_learning_wins_regression`** — Uses confidence 1.0, should still override. No change needed.
  5. **Keep `test_learning_no_op_when_same_category`** — Learning agrees with LLM, no override regardless. No change needed.
  6. **Keep `test_no_prediction_available`** — No change needed.
  7. **Add `test_multi_category_payee_defers_to_llm`** — Learning returns confidence 0.6 (payee used with 2+ categories), LLM chose cat-1. Assert: `result.category_id == 'cat-1'`, no category_explanation change.
  8. **Add `test_single_category_payee_overrides_llm`** — Learning returns confidence 1.0, LLM chose cat-1, learning says cat-2. Assert: `result.category_id == 'cat-2'`, explanation updated.
  9. **Add `test_threshold_boundary_below`** — Learning returns confidence 0.94 (just below threshold). Assert: LLM category preserved.
  10. **Add `test_threshold_boundary_at`** — Learning returns confidence 0.95 (exactly at threshold). Assert: learning overrides.

## Constraints & Architecture
- The 0.95 threshold is chosen because `confidence = best_count / total_count`. A confidence of 0.95 means at least 95% of all uses of this payee went to one category — effectively a "single-category" payee with perhaps 1 outlier. This is a conservative threshold that preserves the current "always override" behavior for unambiguous payees while protecting multi-category ones.
- `predict_category` already returns all the needed data; no DB or repository changes required.
- No UI-facing string changes (the explanation string template remains the same for overrides).

## Verification
- [ ] Run `pytest tests/test_expense_service.py::TestEnhanceWithLearning -v` — all tests pass
- [ ] Run full test suite `pytest` — no regressions
- [ ] Manual test: register "Movistar" expenses in two different categories, then send a message with a contextual hint — the LLM's choice should be preserved
