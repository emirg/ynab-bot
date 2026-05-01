# Plan: Additional Behavioral Fixtures

## Objective & Context
- **Status:** Draft
- **Source Spec:** `docs/specs/2026-05-01-additional-behavioral-fixtures.md`
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
- [ ] Complete or explicitly defer E.25 Behavioral Coverage Index.
- [ ] Choose the first fixture batch from the candidate high-risk flows.

## Implementation Steps
*(Models MUST mark steps with [x] as they are completed and save the file)*

### Group 1
<!-- Fixture selection. -->

#### [ ] Step 1: Select first fixture batch
- **Files:** `docs/plans/2026-05-01-additional-behavioral-fixtures.md`
- **Action:** Replace candidate placeholders with the selected fixtures and rationale before code changes.
- **Tests:** None.

### Group 2 (depends on: Group 1)
<!-- Fixture implementation. -->

#### [ ] Step 2: Implement fixture assertions
- **Files:** `scripts/harness/behavioral_invariants.py`
- **Action:** Add explicit assertion functions for the selected high-risk financial flows using in-memory data and fake repositories where needed.
- **Tests:** `tests/harness/test_checks.py` — failure mode coverage.

#### [ ] Step 3: Register fixture metadata and evidence
- **Files:** `scripts/harness/behavioral_invariants.toml`
- **Action:** Add manifest entries for each fixture with owner path, protected rule, pytest evidence, and doc/ADR evidence.
- **Tests:** `tests/harness/test_checks.py` — manifest validation coverage.

### Group 3 (depends on: Group 2)
<!-- Reporting and close-out. -->

#### [ ] Step 4: Align direct CLI expectations
- **Files:** `tests/harness/test_repository_docs.py`
- **Action:** Update expected behavioral fixture counts and JSON assertions.
- **Tests:** `.venv/bin/pytest tests/harness -q`.

#### [ ] Step 5: Close documentation state
- **Files:** `docs/adrs/2026-04-30-executable-harness-gates.md`, `ROADMAP.md`, `docs/wip_state.md`, archived SPEC/PLAN.
- **Action:** Mark implementation complete, archive docs, and record verification.
- **Tests:** `.venv/bin/python scripts/harness/check_docs.py`.

## Constraints & Architecture
- Keep fixtures deterministic and free of network, database, Telegram, OpenAI, and YNAB API calls.
- Do not duplicate broad pytest behavior; select only rules with deploy-risk value.
- Preserve explicit assertion mappings.
- Treat discovered product drift as a bug rather than weakening the fixture.

## Verification
- [ ] `.venv/bin/python scripts/harness/check_behavioral_invariants.py --json`
- [ ] `.venv/bin/python scripts/harness/check_docs.py`
- [ ] `.venv/bin/python scripts/harness/verify.py --ci --json`
- [ ] `.venv/bin/pytest tests/harness -q`
- [ ] `.venv/bin/pytest`
