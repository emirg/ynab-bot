# Plan: Runtime Financial Invariant Harness

## Objective & Context
- **Status:** Completed
- **Source Spec:** `docs/specs/archive/2026-05-01-runtime-financial-invariant-harness.md`
- **Harness Roadmap Marker:** E.22
- **Goal:** Add deterministic harness checks that protect the repo's core financial invariants.
- **Approach:** Extend the existing standard-library harness with an evidence map for financial source/test/doc patterns, add focused tests, run the existing repo-level harness test, then archive the completed SPEC/PLAN and update ROADMAP.

## Affected Components
- `scripts/harness/checks.py` — add financial invariant checks to `run_checks`.
- `scripts/harness/check_financial_invariants.py` — direct advisory financial invariant command.
- `scripts/harness/commands.py` — command registry entry for the direct diagnostic command.
- `tests/harness/test_checks.py` — add fixture-level coverage for pass/fail behavior.
- `tests/harness/test_repository_docs.py` — repo-level CLI coverage.
- `docs/harness/COMMANDS.md` — document the direct diagnostic command.
- `docs/specs/2026-05-01-runtime-financial-invariant-harness.md` — source SPEC.
- `docs/plans/2026-05-01-runtime-financial-invariant-harness.md` — implementation PLAN.
- `docs/adrs/2026-04-30-executable-harness-gates.md` — expanded harness policy.
- `ROADMAP.md` — completed E.22 entry at closeout.
- `docs/wip_state.md` — handoff state at closeout.

## Prerequisites (Manual)
- [x] User approved the runtime financial invariant harness agenda item.
- [x] Spec framework ADR selected lightweight SPDD-style safeguards without adopting OpenSPDD.

## Implementation Steps
*(Models MUST mark steps with [x] as they are completed and save the file)*

### Group 1
<!-- Tests first for the new harness behavior. -->

#### [x] Step 1: Add financial invariant fixture tests
- **Files:** `tests/harness/test_checks.py`
- **Action:** Add tests proving the harness passes a minimal repo with required financial evidence and fails when required evidence is missing.
- **Tests:** `.venv/bin/pytest tests/harness/test_checks.py -q`.

### Group 2 (depends on: Group 1)
<!-- Harness implementation. -->

#### [x] Step 2: Implement financial invariant checks
- **Files:** `scripts/harness/checks.py`, `scripts/harness/check_financial_invariants.py`, `scripts/harness/commands.py`, `docs/harness/COMMANDS.md`
- **Action:** Add a standard-library evidence map, `check_financial_invariants()`, and a direct advisory command to validate docs, source, and tests for the financial read matrix.
- **Tests:** `.venv/bin/pytest tests/harness/test_checks.py -q`.

### Group 3 (depends on: Group 2)
<!-- Closeout and verification. -->

#### [x] Step 3: Close documentation lifecycle
- **Files:** `docs/specs/2026-05-01-runtime-financial-invariant-harness.md`, `docs/plans/2026-05-01-runtime-financial-invariant-harness.md`, `ROADMAP.md`, `docs/adrs/2026-04-30-executable-harness-gates.md`, `docs/wip_state.md`
- **Action:** Mark SPEC/PLAN complete, archive them, add ROADMAP E.22, and update handoff state.
- **Tests:** `.venv/bin/python scripts/harness/check_docs.py`, `.venv/bin/python scripts/harness/verify.py --ci --json`, `.venv/bin/pytest tests/harness -q`.

## Constraints & Architecture
- Use only Python standard library in harness code.
- Do not call YNAB or require runtime environment variables.
- Prefer explicit evidence over broad source scanning.
- Keep current command interfaces stable.
- Preserve existing documentation lifecycle checks.

## Verification
- [x] `.venv/bin/python scripts/harness/check_docs.py`
- [x] `.venv/bin/python scripts/harness/verify.py --ci --json`
- [x] `.venv/bin/pytest tests/harness -q`
- [x] `.venv/bin/pytest`
