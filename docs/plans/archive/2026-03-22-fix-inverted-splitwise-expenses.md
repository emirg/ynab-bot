# Plan: Fix Inverted Splitwise Expense Bugs

## Objective & Context
- **Status:** Completed
- **Goal:** Fix two bugs in shared expense handling: (1) inverted category assignment for non-50/50 proportion splits, and (2) precision loss when users specify fixed amounts for the other person's share.
- **Why:** When a user says "36700.5 son por Eli" (fixed amount for the other person), the LLM converts it to a proportion, which gets converted back to an amount, losing precision and potentially inverting which share goes to which category. The root cause is ambiguous proportion semantics (user's share vs other's share) and lack of a fixed-amount field.

## Bug Analysis

### Bug 1: Ambiguous proportion semantics
The LLM prompt says `proportion` represents the user's fraction, but the wording is ambiguous. When a user says "2/3 son por Juan" (2/3 is Juan's), the LLM may return `proportion: "2/3"` meaning Juan's share. The code in `to_ynab_format()` treats `split_proportion` as the **user's share**, so it assigns 2/3 of the total to the user's real category and 1/3 to Splitwise — the exact inverse of what was intended.

### Bug 2: Precision loss on fixed amounts
When the user says "36700.5 son por Eli" out of a 60000 total, the LLM must convert to a proportion (0.6117...), then the code converts back to an amount. This round-trip loses precision. The fix is to allow the LLM to return a `split_amount` directly.

## Affected Components
- `src/parsers/llm_expense_parser.py` — Add `split_amount` field to shared_expense JSON schema; clarify that `proportion` is always the **user's fraction**
- `src/domain/models/expense.py` — Add `split_fixed_amount: Optional[Decimal]` field; update `to_ynab_format()` to use it when set
- `src/application/services/expense_service.py` — Parse `split_amount` from LLM response; set `split_fixed_amount` on expense in `_process_shared_expense` and `prepare_shared_expense`
- `src/presentation/telegram/formatters.py` — Display fixed amounts when available instead of computing from proportion
- `tests/test_domain_models.py` — Tests for new `split_fixed_amount` logic in `to_ynab_format()`
- `tests/test_expense_service.py` — Tests for `split_amount` parsing and propagation
- `tests/test_formatters.py` — Tests for fixed-amount display
- `tests/test_llm_expense_parser.py` — Tests for `split_amount` field validation

## Prerequisites (Manual)
- [ ] None — no env vars, infrastructure, or DB changes required

## Implementation Steps
*(Models MUST mark steps with [x] as they are completed and save the file)*

### Group 1: Domain model — add `split_fixed_amount` field and update `to_ynab_format()`
<!-- Core data model change that everything else depends on -->

#### [x] Step 1: Add `split_fixed_amount` field and update `to_ynab_format()`
- **Files:** `src/domain/models/expense.py`
- **Action:**
  1. Add field `split_fixed_amount: Optional[Decimal] = None` to the `Expense` dataclass (after `split_proportion`).
  2. In `to_ynab_format()`, for the **other-paid split** branch (line 61-69):
     - If `self.split_fixed_amount` is set, compute `user_share_milliunits = int(self.split_fixed_amount * -1000)` (the fixed amount IS the user's share — see semantics note below).
     - Otherwise, keep existing logic: `int(self.amount * self.split_proportion * -1000)`.
  3. In `to_ynab_format()`, for the **user-paid split** branch (line 72-81):
     - If `self.split_fixed_amount` is set, compute `split_share = int(self.split_fixed_amount * -1000)` (the fixed amount is the OTHER person's share). Then `user_share = amount_milliunits - split_share`.
     - Otherwise, keep existing logic: `user_share = int(self.amount * self.split_proportion * -1000)`.

  **Semantics clarification for `split_fixed_amount`:**
  - For **user-paid** splits: `split_fixed_amount` = the other person's share (what goes to Splitwise category). The user said "36700 son por Juan" meaning Juan owes 36700.
  - For **other-paid** splits: `split_fixed_amount` = the user's share (what the user owes). The user said "mi parte son 36700" meaning the user owes 36700.
  - This matches natural language: the amount always refers to what the *mentioned person* owes.

  **WAIT — simpler approach:** `split_fixed_amount` always represents the OTHER person's share (Splitwise amount). For user-paid: "36700 son por Juan" → `split_fixed_amount = 36700` → Splitwise gets 36700, user gets (total - 36700). For other-paid: the user owes (total - split_fixed_amount) to the real category. This is more consistent.

  **Final semantics:** `split_fixed_amount` = the amount that goes to the Splitwise tracking category (the other person's share/debt).
  - User-paid: `split_share = split_fixed_amount`, `user_share = total - split_fixed_amount`
  - Other-paid: `user_share (outflow to real category) = total - split_fixed_amount`, `split_share (inflow from splitwise) = -(total - split_fixed_amount)` ... No, this breaks the zero-sum logic.

  **Revised final semantics — keep it simple and unambiguous:**
  `split_fixed_amount` = the amount the OTHER person is responsible for. In the LLM prompt, we ask: "if the user specifies a fixed amount for the other person, return it in `split_amount`."
  - User-paid split: Splitwise category gets `split_fixed_amount`, real category gets `total - split_fixed_amount`.
  - Other-paid split: User's debt (outflow) = `total - split_fixed_amount`. The splitwise inflow cancels this to make the transaction zero-sum. If `split_fixed_amount` is not set but proportion is, fall back to proportion-based computation.

  Implementation in `to_ynab_format()`:
  ```
  # Other-paid branch:
  if self.split_fixed_amount is not None:
      others_share_milliunits = int(self.split_fixed_amount * -1000)
      user_debt_milliunits = int(self.amount * -1000) - others_share_milliunits
  else:
      user_debt_milliunits = int(self.amount * self.split_proportion * -1000)
  # subtransactions: [user_debt outflow, -user_debt inflow to splitwise]

  # User-paid branch:
  if self.split_fixed_amount is not None:
      split_share = int(self.split_fixed_amount * -1000)
      user_share = amount_milliunits - split_share
  else:
      user_share = int(self.amount * self.split_proportion * -1000)
      split_share = amount_milliunits - user_share
  ```

- **Tests:** `tests/test_domain_models.py` — Add test cases:
  1. User-paid split with `split_fixed_amount=Decimal('36700')` on total 60000: verify user_share subtransaction = -23300000 milliunits, split_share = -36700000 milliunits.
  2. Other-paid split with `split_fixed_amount=Decimal('30000')` on total 60000: verify user debt = -30000000, splitwise inflow = 30000000.
  3. Existing proportion-based tests still pass (no `split_fixed_amount` set).
  4. Edge case: `split_fixed_amount=Decimal('0')` — user pays everything, nothing to splitwise.

### Group 2: LLM prompt and service layer (depends on: Group 1)
<!-- These two files have no dependency on each other but both depend on the domain model change -->

#### [x] Step 2: Update LLM prompt — clarify proportion semantics and add `split_amount` field
- **Files:** `src/parsers/llm_expense_parser.py`
- **Action:**
  1. In `_generate_message_system_prompt()`, update the shared_expense JSON schema to add `split_amount`:
     ```json
     "split_amount": <number_or_null>,
     ```
  2. Update rule 7 to clearly distinguish three cases:
     - **proportion**: Always the USER's fraction of the total. "a medias" = `"1/2"`, "mi parte es 1/3" = `"1/3"`, "2/3 son míos" = `"2/3"`. CRITICAL: this is ALWAYS the user's share, never the other person's.
     - **split_amount**: When the user specifies a FIXED AMOUNT for the other person (e.g., "36700 son por Juan", "la parte de Eli es 25000"), return that amount in `split_amount` and set `proportion` to null.
     - **default**: If neither proportion nor split_amount is specified, both are null → defaults to 50/50.
  3. Add examples:
     - "gasté 60000 en restaurantes con Juan, 2/3 son míos" → `proportion: "2/3"`, `split_amount: null` (user's share is 2/3)
     - "gasté 60000 en restaurantes, 36700 son por Juan" → `proportion: null`, `split_amount: 36700` (Juan's fixed amount)
     - "almuerzo 50000 a medias con Eli" → `proportion: "1/2"`, `split_amount: null`
     - "Eli pagó 100k por mí" → `proportion: "1"`, `payer: "other"` (user owes 100%)
  4. Add `split_amount` to the validation in `parse_message()`: if present and is a valid number > 0, keep it; otherwise set to None.
- **Tests:** `tests/test_llm_expense_parser.py` — Add test for `split_amount` field validation: verify that when LLM returns `split_amount: 36700`, it passes validation. Verify that `split_amount: null` or missing is accepted. Verify that `split_amount: -100` or `split_amount: "abc"` is normalized to None.

#### [x] Step 3: Update expense service to parse and propagate `split_fixed_amount`
- **Files:** `src/application/services/expense_service.py`
- **Action:**
  1. In `_process_shared_expense()` (line 400), after building the expense and setting split fields:
     - Read `split_amount = parsed.get('split_amount')` from the LLM response.
     - If `split_amount` is a valid positive number, set `expense.split_fixed_amount = Decimal(str(split_amount))`.
  2. In `prepare_shared_expense()` (line 207), same logic — read `split_amount` from parsed response and set on expense.
  3. Extract the shared logic into a small helper `_apply_split_fields(expense, parsed, split_group, proportion, payer)` to avoid duplication between the two methods. This helper sets: `is_split`, `split_person`, `split_proportion`, `split_category_id`, `split_category_name`, `payer`, and `split_fixed_amount`.
- **Tests:** `tests/test_expense_service.py` — Add test cases:
  1. Shared expense with `split_amount: 36700` in LLM response: verify `expense.split_fixed_amount == Decimal('36700')`.
  2. Shared expense with `split_amount: null`: verify `expense.split_fixed_amount is None`.
  3. Shared expense with custom proportion `1/3` and no `split_amount`: verify proportion is correctly applied and `split_fixed_amount` is None.
  4. `prepare_shared_expense` with `split_amount`: verify it propagates to the returned expense.

### Group 3: Formatter updates (depends on: Group 1)
<!-- Formatter only depends on the domain model, not on the service or parser -->

#### [x] Step 4: Update formatters to display fixed amounts
- **Files:** `src/presentation/telegram/formatters.py`
- **Action:**
  1. In `format_success()` and `format_preview()`, for both `is_split` branches (user-paid and other-paid):
     - If `expense.split_fixed_amount` is set, compute shares from it instead of proportion:
       - User-paid: `split_share = int(expense.split_fixed_amount)`, `user_share = int(expense.amount) - split_share`. Display amounts without percentage (e.g., "Tu parte: $23,300" and "Splitwise: $36,700" instead of "Tu parte (39%): ...").
       - Other-paid: `user_share = int(expense.amount) - int(expense.split_fixed_amount)`. Display "Tu deuda: $30,000" without percentage.
     - If `split_fixed_amount` is not set, keep existing percentage-based display logic.
  2. Factor out the share computation into a small helper to avoid duplicating the if/else in both `format_success` and `format_preview`.
- **Tests:** `tests/test_formatters.py` — Add test cases:
  1. User-paid split with `split_fixed_amount=Decimal('36700')`: verify output shows fixed amounts without percentages.
  2. Other-paid split with `split_fixed_amount=Decimal('25000')`: verify output shows fixed user debt.
  3. Existing proportion-based tests still pass.

## Constraints & Architecture
- **Milliunits invariant**: All YNAB amounts are x1000, expenses are negative. The `split_fixed_amount` field stores the amount in user-facing units (not milliunits) — conversion to milliunits happens only in `to_ynab_format()`, consistent with how `amount` works.
- **No DB changes**: `split_fixed_amount` is a transient field on the `Expense` dataclass — it's computed per-request from LLM output, never persisted. No migration needed.
- **Backward compatibility**: When `split_fixed_amount` is None (the default), all existing behavior is preserved. The proportion-based path is untouched.
- **LLM prompt change is the riskiest part**: The LLM may still return ambiguous proportions. The prompt must be very explicit with examples. The `split_amount` field gives users an escape hatch when proportions are lossy.
- **UI language**: All user-facing strings must remain in Spanish.

## Verification
- [ ] Run full test suite: `.venv/bin/pytest` — all existing tests pass
- [ ] Manual test: Send "gasté 60000 en restaurantes, 36700 son por Eli" — verify Splitwise gets 36700 and real category gets 23300
- [ ] Manual test: Send "almuerzo 50000 a medias con Juan" — verify 50/50 split (25000 each)
- [ ] Manual test: Send "gasté 90000 en mercado con Juan, 2/3 son míos" — verify user gets 60000 in real category, Juan gets 30000 in Splitwise
- [ ] Manual test: Send "Eli gastó 80000 en restaurantes por mí" — verify user debt is 80000 (proportion=1, payer=other)
