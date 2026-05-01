# Plan: Additional Behavioral Fixtures

## Objective & Context
- **Status:** Completed
- **Source Spec:** `docs/specs/archive/2026-05-01-additional-behavioral-fixtures.md`
- **Harness Roadmap Marker:** E.26 — Additional Behavioral Fixtures
- **Goal:** Expand executable behavioral invariant coverage for the next tier of high-risk financial flows.
- **Approach:** After the coverage index exists, select a small fixture batch, implement deterministic assertions, register each fixture in the manifest, and verify the harness remains fast and dependency-light.

## Affected Components
- `scripts/harness/behavioral_invariants.toml` — register new fixture metadata and evidence.
- `scripts/harness/behavioral_invariants.py` — add explicit assertion functions for selected flows.
- `tests/harness/test_checks.py` — add harness-level pass/fail coverage for new fixture registration and failure modes.
- `tests/harness/test_repository_docs.py` — update direct CLI expectations if fixture count changes.
- Relevant source modules — only if a fixture exposes a real product defect that must be fixed.
- `docs/adrs/2026-04-30-executable-harness-gates.md`, `ROADMAP.md`, `docs/wip_state.md` — close-out updates when implemented.

## Prerequisites (Manual)
- [x] Complete or explicitly defer E.25 Behavioral Coverage Index.
- [x] Choose the first fixture batch from the candidate high-risk flows.

## Implementation Steps
*(Models MUST mark steps with [x] as they are completed and save the file)*

### Group 1
<!-- Fixture selection. -->

#### [x] Step 1: Select first fixture batch
- **Files:** `docs/plans/2026-05-01-additional-behavioral-fixtures.md`
- **Action:** Selected shared-expense construction and account balance source selection.
  - **Shared-expense construction**: Protects zero-sum logic for other-paid splits and correct subtransaction allocation in `Expense.to_ynab_format`.
  - **Account balance source**: Protects that `/saldo <cuenta>` reads account fields (`balance`, `cleared_balance`) directly instead of deriving from transactions, adhering to the financial read matrix.
- **Tests:** None.

### Group 2 (depends on: Group 1)
<!-- Fixture implementation. -->

#### [x] Step 2: Implement fixture assertions
- **Files:** `scripts/harness/behavioral_invariants.py`
- **Action:** Added `_assert_shared_expense_construction_preserves_zero_sum` and `_assert_account_balance_reads_from_account_fields`. Fixed dynamic module loader to register in `sys.modules`.
- **Tests:** `tests/harness/test_checks.py` — failure mode coverage.

#### [x] Step 3: Register fixture metadata and evidence
- **Files:** `scripts/harness/behavioral_invariants.toml`
- **Action:** Added manifest entries for the two new fixtures with full coverage index metadata.
- **Tests:** `tests/harness/test_checks.py` — manifest validation coverage.

### Group 3 (depends on: Group 2)
<!-- Reporting and close-out. -->

#### [x] Step 4: Align direct CLI expectations
- **Files:** `tests/harness/test_repository_docs.py`
- **Action:** Updated expected behavioral fixture count to 8.
- **Tests:** `.venv/bin/pytest tests/harness -q`.

#### [x] Step 5: Close documentation state
- **Files:** `docs/adrs/2026-04-30-executable-harness-gates.md`, `ROADMAP.md`, `docs/wip_state.md`, archived SPEC/PLAN.
- **Action:** Marked implementation complete and archived docs.
- **Tests:** `.venv/bin/python scripts/harness/check_docs.py`.

## Constraints & Architecture
- Keep fixtures deterministic and free of network, database, Telegram, OpenAI, and YNAB API calls.
- Do not duplicate broad pytest behavior; select only rules with deploy-risk value.
- Preserve explicit assertion mappings.
- Treat discovered product drift as a bug rather than weakening the fixture.

## Verification
- [x] `.venv/bin/python scripts/harness/check_behavioral_invariants.py --json`
- [x] `.venv/bin/python scripts/harness/check_docs.py`
- [x] `.venv/bin/python scripts/harness/verify.py --ci --json`
- [x] `.venv/bin/pytest tests/harness -q`
- [x] `.venv/bin/pytest`
