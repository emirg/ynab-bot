# Plan: Feed Learning History to LLM Prompt

## Objective & Context
- **Status:** Complete
- **Harness Roadmap:** Ignore
- **Goal:** Pass per-payee category distribution from the learning DB into the LLM prompt, so the LLM can make informed category decisions using both message context and historical usage patterns.
- **Why:** The contextual threshold fix (see `2026-03-22-contextual-learning-threshold.md`) prevents wrong overrides for multi-category payees, but the LLM still has no visibility into what the user has done before. By injecting learning hints into the prompt, the LLM can weigh message context ("Movistar (internet)") against historical patterns ("Movistar: Internet 70%, Teléfono 30%") and make better decisions from the start — eliminating the need for post-hoc overrides entirely for most cases.

## Affected Components
- `src/domain/repositories/learning_repository.py` — add `get_payee_category_distribution` abstract method
- `src/infrastructure/repositories/sqlite_learning_repository.py` — implement `get_payee_category_distribution`
- `src/parsers/llm_expense_parser.py` — add `learning_hints` parameter to `parse_message` and `_generate_system_prompt`; inject hints into prompt
- `src/application/services/expense_service.py` — query learning data before LLM call, pass hints to parser
- `tests/test_sqlite_learning_repository.py` — tests for new repository method
- `tests/test_llm_expense_parser.py` — tests for hint injection in prompt
- `tests/test_expense_service.py` — tests for hint passing in the pipeline

## Prerequisites (Manual)
- [x] Contextual threshold fix (`2026-03-22-contextual-learning-threshold.md`) should be implemented first, as both features interact with `_enhance_with_learning`

## Implementation Steps

### Group 1
<!-- Repository layer: new method to fetch payee-category distribution -->

#### [x] Step 1: Add abstract method to learning repository interface
- **Files:** `src/domain/repositories/learning_repository.py`
- **Action:** Add abstract method `get_payee_category_distribution(self, telegram_id: int) -> Dict[str, List[Dict]]`. Returns a dict keyed by normalized_payee, where each value is a list of `{"category_name": str, "count": int, "percentage": float}` sorted by count descending. This gives the full distribution for all known payees for a user. Only include payees with 2+ total uses (avoid noise from single-use payees).
- **Tests:** No tests for abstract interface.

#### [x] Step 2: Implement `get_payee_category_distribution` in SQLite repository
- **Files:** `src/infrastructure/repositories/sqlite_learning_repository.py`
- **Action:** Implement the method. Query:
  ```sql
  SELECT normalized_payee, category_name, count
  FROM payee_category_mappings
  WHERE telegram_id = ?
  ORDER BY normalized_payee, count DESC
  ```
  Then group by `normalized_payee` in Python. For each payee, compute `total = sum(counts)`, filter to payees with `total >= 2`, and for each category compute `percentage = count / total`. Return the dict structure.
- **Tests:** `tests/test_sqlite_learning_repository.py` —
  - Test with no data returns empty dict
  - Test with single-category payee (total >= 2) returns correct distribution
  - Test with multi-category payee returns sorted list with percentages
  - Test payees with total < 2 are excluded
  - Test per-user isolation (user A data not in user B result)

### Group 2 (depends on: Group 1)
<!-- LLM parser: accept and inject learning hints into prompt -->

#### [x] Step 3: Add learning hints support to LLM parser
- **Files:** `src/parsers/llm_expense_parser.py`
- **Action:**
  1. Add `learning_hints: Optional[str] = None` parameter to `parse_message()` and `parse_expense()`.
  2. Pass `learning_hints` through to `_generate_system_prompt()` / `_generate_message_system_prompt()`.
  3. In the system prompt, add a new section after categories (before the response format):
     ```
     HISTORIAL DE CATEGORIZACIÓN DEL USUARIO:
     Estos son los patrones de categorización previos del usuario. Úsalos como contexto adicional,
     pero PRIORIZA las pistas del mensaje actual (ej: si dice "internet", elige la categoría de internet
     aunque el historial muestre otra categoría como más frecuente).

     {learning_hints}
     ```
  4. If `learning_hints` is None or empty, omit the section entirely (no empty block in prompt).
- **Tests:** `tests/test_llm_expense_parser.py` —
  - Test that `_generate_message_system_prompt` includes the hints section when hints are provided
  - Test that the hints section is omitted when hints is None/empty
  - Test that `parse_message` passes hints through (mock the OpenAI client, inspect the system prompt)

### Group 3 (depends on: Group 1, Group 2)
<!-- Wire it all together in ExpenseService -->

#### [x] Step 4: Build learning hints string in ExpenseService
- **Files:** `src/application/services/expense_service.py`
- **Action:**
  1. Add private method `_build_learning_hints(self, telegram_user_id: int) -> Optional[str]`:
     - Call `self.learning_repository.get_payee_category_distribution(telegram_user_id)`
     - If empty, return None
     - Format as a compact string, max 20 payees (sorted by total usage descending), e.g.:
       ```
       - McDonald's: 🥗 Meal delivery (90%), 🛒 Groceries (10%)
       - Movistar: 📶 Internet (65%), 📱 Teléfono (35%)
       - Éxito: 🛒 Groceries (100%)
       ```
     - Cap at 20 payees to keep prompt size manageable (LLM token budget)
  2. In every code path that calls `self.llm_parser.parse_message()` (there are ~3 call sites: `process_message`, `prepare_expense`, and shared expense paths), call `_build_learning_hints` first and pass the result:
     ```python
     learning_hints = self._build_learning_hints(telegram_user_id)
     parsed = self.llm_parser.parse_message(message, timezone_str=user_tz, learning_hints=learning_hints)
     ```
  3. Same for `parse_expense()` calls (voice handler path).
- **Tests:** `tests/test_expense_service.py` —
  - Test `_build_learning_hints` returns None when no distribution data
  - Test `_build_learning_hints` formats correctly with multi-category payee
  - Test `_build_learning_hints` caps at 20 payees
  - Test that `process_message` passes learning_hints to the parser (verify mock call args)
  - Test that `prepare_expense` passes learning_hints to the parser

#### [x] Step 5: Pass learning hints in receipt and voice paths
- **Files:** `src/application/services/expense_service.py`
- **Action:** For `process_receipt_image()` and `process_expense_message()` (voice path), also build and pass learning hints to the respective parser calls. For receipts, this goes to `parse_receipt_image()` which will need the same `learning_hints` parameter added.
- **Tests:** `tests/test_expense_service.py` —
  - Test receipt path passes learning_hints
  - Test voice path passes learning_hints

### Group 4 (depends on: Group 3)
<!-- Add learning hints to receipt parser -->

#### [x] Step 6: Add learning hints support to receipt parser
- **Files:** `src/parsers/llm_expense_parser.py`
- **Action:** Add `learning_hints: Optional[str] = None` parameter to `parse_receipt_image()`. Inject into `_generate_receipt_system_prompt()` with the same pattern as the message prompt.
- **Tests:** `tests/test_llm_expense_parser.py` —
  - Test receipt prompt includes hints when provided
  - Test receipt prompt omits hints section when None

## Constraints & Architecture
- **Token budget**: The learning hints section adds tokens to every LLM call. Cap at 20 payees (~400 tokens max). This is acceptable for GPT-4o-mini given the existing prompt is already ~1000+ tokens.
- **Performance**: `get_payee_category_distribution` is called once per user message. Since it's a simple indexed query on `(telegram_id)`, latency is negligible compared to the LLM call.
- **Interaction with contextual threshold**: Once this feature is implemented, `_enhance_with_learning` becomes a safety net for cases where the LLM ignores the hints. The threshold fix ensures it only overrides for unambiguous payees (confidence >= 0.95), while this feature gives the LLM the information to make correct choices for ambiguous ones.
- **Prompt wording**: The hint text must explicitly tell the LLM to prioritize message context over historical patterns. Otherwise the LLM might blindly follow the majority category, which defeats the purpose.
- **Backward compatibility**: All new parameters are optional with defaults. Existing callers that don't pass hints continue to work.
- **UI language**: All prompt text in Spanish, matching existing conventions.

## Verification
- [x] Run full test suite `pytest` — no regressions
- [x] Manual test: register several "Movistar" expenses across "Internet" and "Teléfono" categories
- [x] Send "Movistar (internet)" — should categorize as Internet (LLM sees the hint distribution + message context)
- [x] Send "Movistar (teléfono)" — should categorize as Teléfono
- [x] Send just "Movistar 50k" — should use the majority category from history
- [x] Verify prompt size stays reasonable (inspect logs or add temporary debug logging)
