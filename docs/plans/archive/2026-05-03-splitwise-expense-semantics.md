# Plan: Splitwise Expense Semantics

## Objective & Context
- **Status:** Completed
- **Source Spec:** `docs/specs/archive/2026-05-03-splitwise-expense-semantics.md`
- **Harness Roadmap Marker:** ### E.31 — Splitwise Responsibility Semantics [COMPLETADO]
- **Goal:** Make shared-expense parsing and YNAB transaction construction deterministic for payer/responsibility cases, including 100% ownership and fixed-share messages.
- **Approach:** Add an internal normalized share contract in the domain/service layer, update shared-expense construction to derive YNAB payloads from user/other responsibility, strengthen the LLM prompt output fields, and lock the behavior matrix with tests. Keep HTTP response compatibility unchanged.

## Affected Components
- `src/domain/models/expense.py` — Represent normalized user/other shares and generate regular, split, or zero-sum YNAB payloads without zero-amount split legs.
- `src/application/services/expense_service.py` — Normalize parser output into deterministic user/other shares; reject invalid/conflicting share amounts with Spanish errors; skip transaction creation for other-paid zero-user-share cases.
- `src/parsers/llm_expense_parser.py` — Clarify prompt schema and validation for fixed shares owned by the user vs. the other person while preserving compatibility with existing fields.
- `src/presentation/telegram/formatters.py` — Display normalized share results for split, one-category, and no-op/error paths.
- `tests/domain/models/test_domain_models.py` — Cover YNAB payload construction for the behavior matrix and zero-share regular transactions.
- `tests/application/services/test_expense_service.py` — Cover shared-expense normalization, invalid shares, account selection, no-op behavior, and transaction creation calls.
- `tests/parsers/test_llm_expense_parser.py` — Cover validation of user-owned and other-owned fixed share fields.
- `tests/presentation/telegram/test_formatters.py` — Cover preview/success wording for normalized share cases.
- `scripts/harness/behavioral_invariants.toml` and `scripts/harness/behavioral_invariants.py` — Add a behavioral fixture for the core Splitwise behavior matrix.
- `docs/ARCHITECTURE.md` and `README.md` — Update shared-expense docs to separate payer from financial responsibility.

## Prerequisites (Manual)
- [x] SPEC approved by user in the current session.
- [x] No database migration required; share normalization is request-local.
- [x] HTTP serializer remains externally compatible in this implementation.

## Implementation Steps

### Group 1
<!-- Define deterministic domain behavior before service/parser wiring. -->

#### [x] Step 1: Add normalized share fields and domain YNAB payload tests
- **Files:** `src/domain/models/expense.py`, `tests/domain/models/test_domain_models.py`
- **Action:** Add optional request-local fields to `Expense` for normalized responsibility, such as `split_user_share_amount: Optional[Decimal]` and `split_other_share_amount: Optional[Decimal]`. Update `to_ynab_format()` so these fields take precedence over legacy `split_proportion` / `split_fixed_amount`.
- **Tests:** Add tests for:
  - user paid 200k, 50/50 → split subtransactions `-100k` real and `-100k` Splitwise.
  - user paid 100k for Frank → regular transaction categorized only to Splitwise, no `subtransactions`.
  - user paid 200k all user's responsibility → regular transaction categorized only to real category.
  - other paid 200k for user → zero-sum `-200k` real and `+200k` Splitwise.
  - other paid with user share 0 → no domain payload should be requested by service; domain test can document zero-share behavior defensively if needed.

#### [x] Step 2: Preserve legacy proportion/fixed-amount compatibility tests
- **Files:** `tests/domain/models/test_domain_models.py`
- **Action:** Add/adjust tests proving existing proportion-based behavior still works when normalized fields are absent.
- **Tests:** Existing split proportion and `split_fixed_amount` tests must continue passing.

### Group 2 (depends on: Group 1)
<!-- Normalize parser output in the application service. -->

#### [x] Step 3: Add shared-expense share normalization helper tests
- **Files:** `tests/application/services/test_expense_service.py`
- **Action:** Write tests for a service helper that computes user/other shares from parsed fields and total amount.
- **Tests:** Cover:
  - default 50/50 for `payer=user`, `proportion=None`.
  - `proportion=0` for user-paid full other responsibility.
  - `proportion=1` for other-paid full user responsibility.
  - `user_share_amount=70000` on total 200k.
  - `other_share_amount=70000` on total 200k.
  - fixed amount greater than total rejected.
  - both fixed shares present and sum not equal to total rejected with Spanish message.

#### [x] Step 4: Implement normalization in `ExpenseService`
- **Files:** `src/application/services/expense_service.py`
- **Action:** Add a small internal helper that returns normalized `(user_share, other_share)` or an error message. Apply it in both `_process_shared_expense()` and `prepare_shared_expense()` before account selection and commit. Populate the new `Expense` normalized share fields.
- **Tests:** Run the tests from Step 3 and existing shared-expense service tests.

#### [x] Step 5: Handle other-paid zero-user-share no-op
- **Files:** `src/application/services/expense_service.py`, `tests/application/services/test_expense_service.py`
- **Action:** When normalized `payer == "other"` and `user_share == 0`, return an `ExpenseResult.error_result(...)` with clear Spanish no-op text and do not call `create_transaction`.
- **Tests:** Assert no YNAB transaction is created and the message explains there is no user expense/debt to register.

### Group 3 (depends on: Group 2)
<!-- Parser contract and prompt alignment. -->

#### [x] Step 6: Extend parser schema and validation for owner-specific fixed shares
- **Files:** `src/parsers/llm_expense_parser.py`, `tests/parsers/test_llm_expense_parser.py`
- **Action:** Add compatible optional fields such as `user_share_amount` and `other_share_amount` to the shared-expense schema. Keep `split_amount` accepted for backward compatibility as the other person's share unless owner-specific fields are present.
- **Tests:** Validate numeric positive values, missing/null values, invalid values normalized to `None`, and conflict-preserving behavior for service rejection.

#### [x] Step 7: Update shared-expense prompt examples
- **Files:** `src/parsers/llm_expense_parser.py`, `tests/parsers/test_llm_expense_parser.py`
- **Action:** Update prompt rules and examples to match the SPEC matrix:
  - `con Frank` / `conmigo` default 50/50.
  - `por Frank` / `para Frank` user share 0 when user paid.
  - `por mi` / `para mi` user share 100% when other paid.
  - `70k son mios` maps to `user_share_amount`.
  - `70k son de Frank` maps to `other_share_amount`.
- **Tests:** Prompt-content tests should assert the critical examples are present or parser validation tests should cover the fields.

### Group 4 (depends on: Group 3)
<!-- Presentation and HTTP compatibility. -->

#### [x] Step 8: Update Telegram formatting for normalized shares
- **Files:** `src/presentation/telegram/formatters.py`, `tests/presentation/telegram/test_formatters.py`
- **Action:** Teach `_compute_split_shares()` to prefer normalized share fields. Ensure one-category 100% user-paid cases format as regular expenses with the resolved category. Preserve existing format output for legacy split cases.
- **Tests:** Cover preview/success for user-paid full Splitwise category, user-paid full real category, other-paid fixed user share, and unchanged legacy proportion display.

#### [x] Step 9: Verify HTTP serializer compatibility
- **Files:** `tests/presentation/http/test_http_serializers.py`, `src/presentation/http/serializers.py`
- **Action:** Confirm no public response fields are required. If the new internal fields appear on `Expense`, ensure serializer output remains compatible and excludes them unless already covered by existing generic behavior.
- **Tests:** Existing serializer tests should pass unchanged; add a compatibility assertion only if the new fields risk leaking.

### Group 5 (depends on: Group 4)
<!-- Behavioral harness and documentation close-out. -->

#### [x] Step 10: Add behavioral invariant for Splitwise matrix
- **Files:** `scripts/harness/behavioral_invariants.toml`, `scripts/harness/behavioral_invariants.py`, `tests/harness/test_checks.py`
- **Action:** Add a fixture that constructs representative `Expense` objects for the four primary scenarios and verifies account/category-shape payloads through `to_ynab_format()` or service-level helpers where transaction creation/no-op is relevant.
- **Tests:** Run harness checks and targeted harness tests.

#### [x] Step 11: Update docs
- **Files:** `docs/ARCHITECTURE.md`, `README.md`, `docs/specs/archive/2026-05-03-splitwise-expense-semantics.md`
- **Action:** Update shared-expense documentation to describe payer vs. responsibility, 100% one-category user-paid cases, and other-paid zero-sum behavior. Mark SPEC as implemented only during final close-out, not during implementation.
- **Tests:** `rtk .venv/bin/python scripts/harness/check_docs.py`

#### [x] Step 12: Final verification and review
- **Files:** None
- **Action:** Run targeted tests first, then full local CI harness.
- **Verification:**
  - `rtk .venv/bin/pytest tests/domain/models/test_domain_models.py tests/application/services/test_expense_service.py tests/parsers/test_llm_expense_parser.py tests/presentation/telegram/test_formatters.py tests/presentation/http/test_http_serializers.py`
  - `rtk .venv/bin/python scripts/harness/check_docs.py`
  - `rtk .venv/bin/python scripts/harness/verify.py --ci`
  - `rtk .venv/bin/pytest`

## Constraints & Architecture
- YNAB milliunit invariant: API amounts are x1000 and expenses are negative.
- YNAB source of truth remains unchanged; this work only changes transaction creation from user input.
- No database changes.
- User-facing strings must be Spanish.
- Per-user split alias and shared account lookups remain scoped by `telegram_user_id`.
- Do not break the HTTP serializer contract in this implementation.
- Do not introduce a direct Splitwise API integration.

## Verification
- [x] Behavior matrix scenarios produce expected YNAB account/category shapes.
- [x] User-paid 100% cases create regular one-category transactions, not zero-leg splits.
- [x] Other-paid user-share cases remain zero-sum in `Shared Transactions`.
- [x] Other-paid zero-user-share case does not create a transaction and returns a clear Spanish message.
- [x] Conflicting fixed-share amounts are rejected with a clear Spanish message.
- [x] Documentation and behavioral harness pass.
