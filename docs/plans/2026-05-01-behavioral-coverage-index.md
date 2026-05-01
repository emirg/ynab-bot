# Plan: Behavioral Coverage Index

## Objective & Context
- **Status:** Draft
- **Source Spec:** `docs/specs/2026-05-01-behavioral-coverage-index.md`
- **Goal:** Extend the behavioral invariant manifest into a coverage index linking each protected rule to pytest and documentation evidence.
- **Approach:** Add evidence metadata to the TOML manifest, validate path/snippet references in the existing runner, and update tests and docs without adding new behavioral scenarios.

## Affected Components
- `scripts/harness/behavioral_invariants.toml` — add pytest and documentation evidence entries.
- `scripts/harness/behavioral_invariants.py` — validate evidence metadata and emit fixture-scoped failures.
- `scripts/harness/checks.py` — keep behavioral finding formatting concise with evidence validation failures.
- `tests/harness/test_checks.py` — add fixture repo cases for valid evidence, missing evidence paths, and missing snippets.
- `tests/harness/test_repository_docs.py` — keep direct CLI JSON coverage aligned.
- `docs/adrs/2026-04-30-executable-harness-gates.md` — record the coverage-index policy if implemented.
- `ROADMAP.md`, `docs/wip_state.md` — close-out updates when implemented.

## Prerequisites (Manual)
- [ ] Confirm E.25 is the next implementation item before coding.

## Implementation Steps
*(Models MUST mark steps with [x] as they are completed and save the file)*

### Group 1
<!-- Manifest schema extension. -->

#### [ ] Step 1: Extend manifest evidence schema
- **Files:** `scripts/harness/behavioral_invariants.toml`
- **Action:** Add evidence metadata for current fixtures using standard TOML arrays of tables or equivalent explicit structure.
- **Tests:** No direct tests until parser support exists.

### Group 2 (depends on: Group 1)
<!-- Parser and validation. -->

#### [ ] Step 2: Validate evidence metadata
- **Files:** `scripts/harness/behavioral_invariants.py`
- **Action:** Parse pytest/doc evidence entries, validate required fields, existing paths, and snippet presence.
- **Tests:** `tests/harness/test_checks.py` — missing evidence path and missing snippet failures.

### Group 3 (depends on: Group 2)
<!-- Harness integration and close-out. -->

#### [ ] Step 3: Align reporting and repository tests
- **Files:** `scripts/harness/checks.py`, `tests/harness/test_checks.py`, `tests/harness/test_repository_docs.py`
- **Action:** Ensure evidence validation failures surface as behavioral invariant failures and JSON summaries remain stable.
- **Tests:** `.venv/bin/pytest tests/harness -q`.

#### [ ] Step 4: Close documentation state
- **Files:** `docs/adrs/2026-04-30-executable-harness-gates.md`, `ROADMAP.md`, `docs/wip_state.md`, archived SPEC/PLAN.
- **Action:** Mark docs complete, archive, update ADR references, and refresh handoff.
- **Tests:** `.venv/bin/python scripts/harness/check_docs.py`.

## Constraints & Architecture
- Use standard-library `tomllib`; do not add schema dependencies.
- Do not execute pytest inside the harness.
- Keep the manifest reviewable by humans and agents.
- Preserve the current Railway `verify.py --ci` blocking behavior.

## Verification
- [ ] `.venv/bin/python scripts/harness/check_behavioral_invariants.py --json`
- [ ] `.venv/bin/python scripts/harness/check_docs.py`
- [ ] `.venv/bin/python scripts/harness/verify.py --ci --json`
- [ ] `.venv/bin/pytest tests/harness -q`
- [ ] `.venv/bin/pytest`
