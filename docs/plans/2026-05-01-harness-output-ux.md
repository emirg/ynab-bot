# Plan: Harness Output UX

## Objective & Context
- **Status:** Draft
- **Source Spec:** `docs/specs/2026-05-01-harness-output-ux.md`
- **Goal:** Make harness diagnostics easier to scan locally and in Railway logs while preserving existing command behavior.
- **Approach:** Improve formatting and optional metadata in the shared harness output layer, then update focused tests without changing check semantics.

## Affected Components
- `scripts/harness/checks.py` — shared `Finding` model and text/JSON formatting.
- `scripts/harness/check_docs.py` — verify output remains compatible.
- `scripts/harness/check_financial_invariants.py` — verify direct command output remains compatible.
- `scripts/harness/check_behavioral_invariants.py` — verify direct command output remains compatible.
- `scripts/harness/verify.py` — verify CI behavior remains compatible.
- `tests/harness/test_checks.py` — formatting and exit-code contract coverage.
- `tests/harness/test_repository_docs.py` — repo-level JSON CLI coverage.
- `docs/harness/COMMANDS.md`, `ROADMAP.md`, `docs/wip_state.md` — close-out updates if needed.

## Prerequisites (Manual)
- [ ] Decide whether E.27 should be implemented before or after E.25/E.26.
- [ ] Decide whether the first UX slice should add optional check-family metadata or only revise text formatting.

## Implementation Steps
*(Models MUST mark steps with [x] as they are completed and save the file)*

### Group 1
<!-- Output design lock. -->

#### [ ] Step 1: Choose output shape
- **Files:** `docs/plans/2026-05-01-harness-output-ux.md`
- **Action:** Record whether implementation will add `Finding` metadata, text-only formatting improvements, or both.
- **Tests:** None.

### Group 2 (depends on: Group 1)
<!-- Shared formatter implementation. -->

#### [ ] Step 2: Update shared formatter
- **Files:** `scripts/harness/checks.py`
- **Action:** Improve text formatting and optionally add backwards-compatible JSON metadata while preserving `summary` and `findings`.
- **Tests:** `tests/harness/test_checks.py` — pass/warn/fail grouping and JSON compatibility.

### Group 3 (depends on: Group 2)
<!-- Command compatibility and close-out. -->

#### [ ] Step 3: Verify command contracts
- **Files:** `tests/harness/test_repository_docs.py`
- **Action:** Ensure all direct harness commands still return expected exit codes and valid JSON.
- **Tests:** `.venv/bin/pytest tests/harness -q`.

#### [ ] Step 4: Close documentation state
- **Files:** `docs/adrs/2026-04-30-executable-harness-gates.md`, `ROADMAP.md`, `docs/wip_state.md`, archived SPEC/PLAN.
- **Action:** Mark implementation complete, archive docs, and record verification.
- **Tests:** `.venv/bin/python scripts/harness/check_docs.py`.

## Constraints & Architecture
- Preserve all current command names and exit-code behavior.
- Do not add non-standard-library formatting dependencies.
- Keep JSON backwards-compatible.
- Keep output deterministic for tests and deploy logs.

## Verification
- [ ] `.venv/bin/python scripts/harness/check_docs.py`
- [ ] `.venv/bin/python scripts/harness/check_financial_invariants.py --json`
- [ ] `.venv/bin/python scripts/harness/check_behavioral_invariants.py --json`
- [ ] `.venv/bin/python scripts/harness/verify.py --ci --json`
- [ ] `.venv/bin/pytest tests/harness -q`
- [ ] `.venv/bin/pytest`
