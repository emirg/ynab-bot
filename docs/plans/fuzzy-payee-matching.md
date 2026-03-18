# Plan: Fuzzy Payee Matching

## Objective & Context
- **Status:** Completed
- **Goal:** When creating a transaction, match the user's payee text against existing YNAB payees and reuse the existing payee (via `payee_id`) instead of creating a duplicate with slightly different casing/spelling.
- **Why:** Currently, if a user types "carulla" but YNAB has "Carulla", YNAB's API (which uses case-sensitive `payee_name` matching) creates a brand new payee. Over time this pollutes the user's payee list with duplicates like "carulla", "Carulla", "CARULLA".

## Design Decision: Where to Match

The matching happens in `ExpenseService` (application layer), not in the domain model. Rationale:
- `Expense.to_ynab_format()` is a pure domain method -- it should not need API data.
- `ExpenseService` already fetches categories and accounts from YNAB API per request. Payees follow the same pattern.
- The matching logic is a service concern (orchestration between parsed input and API data).

When a match is found, we set `payee_id` on the Expense and let `to_ynab_format()` emit `payee_id` instead of `payee_name`. When no match is found, we fall back to the current behavior (`payee_name` only).

## Matching Strategy

Use a tiered approach consistent with the existing category/account matching pattern in `ExpenseService`:

1. **Exact match** -- `payee_name == ynab_payee.name` (O(1) dict lookup)
2. **Case-insensitive match** -- `payee_name.lower() == ynab_payee.name.lower()` (O(1) dict lookup)
3. **Normalized match** -- strip accents, punctuation, possessives: `normalize(payee) == normalize(ynab_payee)` (O(1) dict lookup)
4. **Containment match** -- one is a substring of the other (linear scan, only if steps 1-3 fail)

This mirrors the existing `_find_category_id_by_name` pattern exactly.

No external fuzzy matching library (e.g., `fuzzywuzzy`, `rapidfuzz`) is needed. The tiered exact/normalized/containment approach handles the real-world cases (casing, accents, punctuation) without adding a dependency. This is the same strategy already used for categories and accounts.

## Affected Components
- `src/domain/models/expense.py` -- Add optional `payee_id` field; update `to_ynab_format()` to prefer `payee_id` over `payee_name`
- `src/domain/models/user.py` -- Add `YNABPayee` dataclass (id, name, deleted)
- `src/domain/repositories/ynab_repository.py` -- Add abstract `get_payees()` method
- `src/infrastructure/repositories/ynab_api_repository.py` -- Implement `get_payees()` with caching (same pattern as categories/accounts)
- `src/application/services/expense_service.py` -- Add `_match_payee()` method and payee lookup maps; call it before creating the transaction in all three pipelines (expense, shared_expense, receipt)
- `src/domain/services/payee_normalizer.py` -- Extract a `_strip_accents()` utility for reuse in payee matching (optional, may fold into matching logic directly)
- `tests/test_domain_models.py` -- Tests for `payee_id` in `to_ynab_format()`
- `tests/test_expense_service.py` -- Tests for payee matching logic
- `tests/test_ynab_api_repository.py` -- Tests for `get_payees()`

## Prerequisites (Manual)
- [ ] None -- YNAB API `GET /budgets/{budget_id}/payees` is already available and uses the same auth token.

## Implementation Steps

### Group 1: DBA Consultation
<!-- No DB changes needed -- this feature is pure API/application logic. Skip DBA. -->
*Skipped -- no database changes required.*

### Group 1: Domain Model Changes (parallel, no file overlap)

#### [x] Step 1: Add `YNABPayee` domain model
- **Files:** `src/domain/models/user.py`
- **Action:** Add a `YNABPayee` dataclass following the same pattern as `YNABAccount` and `YNABCategory`:
  ```
  @dataclass
  class YNABPayee:
      id: str
      name: str
      deleted: bool = False

      @classmethod
      def from_api_response(cls, data: dict) -> 'YNABPayee':
          return cls(id=data['id'], name=data['name'], deleted=data.get('deleted', False))
  ```
- **Tests:** `tests/test_domain_models.py` -- Test `YNABPayee` creation and `from_api_response()`

#### [x] Step 2: Add `payee_id` to `Expense` and update `to_ynab_format()`
- **Files:** `src/domain/models/expense.py`
- **Action:**
  - Add `payee_id: Optional[str] = None` field to `Expense` dataclass.
  - In `to_ynab_format()`, if `self.payee_id` is set (and valid UUID), use `"payee_id": self.payee_id` instead of `"payee_name": self.payee`. If `payee_id` is not set, keep current `payee_name` behavior.
  - Always include `payee_name` as well for display/memo purposes (YNAB API accepts both; `payee_id` takes precedence when present).
- **Tests:** `tests/test_domain_models.py` -- Test `to_ynab_format()` with `payee_id` set (should include `payee_id` key), without `payee_id` (should only have `payee_name`), and with invalid UUID `payee_id` (should fall back to `payee_name` only).

#### [x] Step 3: Add `get_payees()` to repository interface
- **Files:** `src/domain/repositories/ynab_repository.py`
- **Action:** Add abstract method `get_payees(self, budget_id: str) -> List[YNABPayee]` to the `YNABRepository` ABC. Add import for `YNABPayee`.
- **Tests:** No direct tests needed (abstract method).

### Group 2: Infrastructure (depends on: Group 1)

#### [x] Step 4: Implement `get_payees()` in `YNABApiRepository`
- **Files:** `src/infrastructure/repositories/ynab_api_repository.py`
- **Action:** Implement `get_payees()` following the exact same pattern as `get_accounts()`:
  - Endpoint: `GET /budgets/{budget_id}/payees`
  - Response path: `response.json()["data"]["payees"]`
  - Filter out deleted payees.
  - Cache with the same TTL (`_CACHE_TTL_SECONDS`), key: `payees:{budget_id}`.
  - Return `List[YNABPayee]`.
  - Also add import for `YNABPayee` in the imports section.
- **Tests:** `tests/test_ynab_api_repository.py` -- Test `get_payees()` with mocked HTTP response, test caching behavior, test error handling.

### Group 3: Application Layer (depends on: Group 2)

#### [x] Step 5: Add payee matching to `ExpenseService`
- **Files:** `src/application/services/expense_service.py`
- **Action:**
  1. Add payee lookup maps (same pattern as category/account maps):
     - `self._payee_by_name: Dict[str, Tuple[str, str]] = {}` -- exact name -> (payee_id, canonical_name)
     - `self._payee_by_name_lower: Dict[str, Tuple[str, str]] = {}` -- lowercased -> (payee_id, canonical_name)
     - `self._payee_by_name_normalized: Dict[str, Tuple[str, str]] = {}` -- normalized (no accents/punctuation) -> (payee_id, canonical_name)
  2. In `_update_llm_parser_data()`, also accept payees parameter and build the payee lookup maps. Use `unicodedata.normalize('NFD', ...).encode('ascii', 'ignore').decode()` for accent stripping.
  3. Add method `_match_payee(self, payee_name: str) -> Optional[Tuple[str, str]]` that returns `(payee_id, canonical_name)` or `None`. Matching tiers:
     - Exact match (dict lookup)
     - Case-insensitive match (dict lookup)
     - Normalized match (dict lookup)
     - Containment match (linear scan of `_payee_by_name_lower`)
  4. Call `_match_payee()` in `_build_expense_from_parsed()` right after sanitizing the payee name. If matched, set `expense.payee_id` and update `expense.payee` to the canonical YNAB name.
  5. Update all callers of `_update_llm_parser_data()` to also fetch and pass payees:
     - `process_message()` -- add `payees = ynab_repository.get_payees(user_config.budget_id)`
     - `process_receipt_image()` -- same
     - `process_expense_message()` -- same
- **Tests:** `tests/test_expense_service.py` -- Test `_match_payee()` for each tier (exact, case-insensitive, normalized, containment, no match). Test that `_build_expense_from_parsed()` sets `payee_id` when match found. Test end-to-end `process_message()` with mock payees.

### Group 4: Test coverage pass (depends on: Group 3)

#### [x] Step 6: Verify all tests pass and coverage is maintained
- **Files:** All test files
- **Action:** Run full test suite. Fix any regressions. Ensure coverage stays at ~88%+.
- **Tests:** `pytest` -- full suite

## Constraints & Architecture
- **Milliunits invariant**: Not affected -- this feature only touches payee identification, not amounts.
- **DI via factory**: Payees are fetched via `ynab_repository.get_payees()` on the per-user repository instance -- consistent with existing pattern.
- **Per-user isolation**: Payee list comes from the user's own YNAB budget -- no cross-user leakage.
- **UI language**: No new user-facing strings are introduced. The payee name shown to the user will be the canonical YNAB name (which is what they'd expect).
- **Caching**: Payees are cached with the same 5-minute TTL as categories and accounts. This means if a user creates a new payee in YNAB directly, the bot will pick it up within 5 minutes.
- **No new dependencies**: The matching uses only stdlib (`unicodedata` for accent stripping). No `fuzzywuzzy` or similar.
- **Backward compatibility**: When `payee_id` is `None`, behavior is identical to current. Existing tests should pass without modification.

## Verification
- [ ] Send "almuerzo carulla 50000" when YNAB has payee "Carulla" -- should reuse existing payee (no duplicate created)
- [ ] Send "almuerzo mcdonald's 25000" when YNAB has "McDonald's" -- should match despite apostrophe
- [ ] Send "café exito 15000" when YNAB has "Exito" -- should match despite accent difference
- [ ] Send "almuerzo newplace 30000" when no matching payee exists -- should create new payee (current behavior preserved)
- [ ] Check YNAB payee list after several transactions -- no duplicates
